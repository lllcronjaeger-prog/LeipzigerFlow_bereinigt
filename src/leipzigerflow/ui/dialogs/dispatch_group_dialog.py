from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QSpinBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)
from sqlalchemy import select

from leipzigerflow.models.auth import User
from leipzigerflow.models.contractor import Contractor
from leipzigerflow.models.dispatch_group import DispatchGroup, DispatchGroupRule
from leipzigerflow.models.driver import Driver
from leipzigerflow.models.trailer import Trailer
from leipzigerflow.models.vehicle import Vehicle


class AssignmentTab(QWidget):
    assignment_changed = Signal()

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self._loaded = False
        self.available = QListWidget()
        self.assigned = QListWidget()
        for widget in (self.available, self.assigned):
            widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
            widget.setUniformItemSizes(True)
            widget.itemDoubleClicked.connect(lambda _item, w=widget: self._move_from(w))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen …")
        self.search.textChanged.connect(self._filter)
        buttons = QVBoxLayout()
        for text, fn in ((">", self.add_selected), (">>", self.add_all), ("<", self.remove_selected), ("<<", self.remove_all)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            buttons.addWidget(b)
        buttons.addStretch()
        lists = QHBoxLayout()
        lists.addWidget(self._box("Nicht zugeordnet", self.available))
        lists.addLayout(buttons)
        lists.addWidget(self._box("Zugeordnet", self.assigned))
        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addLayout(lists)

    @staticmethod
    def _box(caption, widget):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel(caption))
        lay.addWidget(widget)
        return box

    def set_items(self, all_items, assigned_ids, label_fn):
        self.setUpdatesEnabled(False)
        try:
            self.available.clear()
            self.assigned.clear()
            available_items = []
            assigned_items = []
            for obj in all_items:
                item = QListWidgetItem(label_fn(obj))
                item.setData(Qt.UserRole, obj.id)
                (assigned_items if obj.id in assigned_ids else available_items).append(item)
            # QListWidget.addItems() accepts strings, not QListWidgetItem objects.
            # Adding item objects via addItems() creates empty rows in PySide6 and can
            # raise a type error depending on the binding version.
            for item in available_items:
                self.available.addItem(item)
            for item in assigned_items:
                self.assigned.addItem(item)
            self._loaded = True
            self._filter(self.search.text())
        finally:
            self.setUpdatesEnabled(True)

    def assigned_ids(self):
        return {self.assigned.item(i).data(Qt.UserRole) for i in range(self.assigned.count())}

    def _move(self, source, target, selected_only):
        selected = source.selectedItems() if selected_only else None
        rows = sorted(
            ({source.row(item) for item in selected} if selected_only else range(source.count())),
            reverse=True,
        )
        if not rows:
            return
        source.setUpdatesEnabled(False)
        target.setUpdatesEnabled(False)
        try:
            moved = [source.takeItem(row) for row in rows]
            # reverse again so the visible ordering remains stable
            for item in reversed(moved):
                target.addItem(item)
        finally:
            source.setUpdatesEnabled(True)
            target.setUpdatesEnabled(True)
        self._filter(self.search.text())
        self.assignment_changed.emit()

    def _move_from(self, source):
        self._move(source, self.assigned if source is self.available else self.available, True)

    def add_selected(self):
        self._move(self.available, self.assigned, True)

    def add_all(self):
        self._move(self.available, self.assigned, False)

    def remove_selected(self):
        self._move(self.assigned, self.available, True)

    def remove_all(self):
        self._move(self.assigned, self.available, False)

    def _filter(self, text):
        needle = text.strip().casefold()
        for widget in (self.available, self.assigned):
            widget.setUpdatesEnabled(False)
            try:
                for i in range(widget.count()):
                    item = widget.item(i)
                    item.setHidden(bool(needle) and needle not in item.text().casefold())
            finally:
                widget.setUpdatesEnabled(True)


class GroupEditorDialog(QDialog):
    def __init__(self, session, group: DispatchGroup | None = None, parent=None):
        super().__init__(parent); self.session=session; self.group=group or DispatchGroup(name="")
        self.setWindowTitle("Dispositionsgruppe bearbeiten"); self.resize(980,680)
        self.tabs=QTabWidget(); self._build_general(); self._build_assignment_tabs(); self._build_rules()
        self.tabs.currentChanged.connect(self._ensure_current_tab_loaded)
        self.summary=QLabel(); self.summary.setStyleSheet("font-weight: bold; padding: 6px;")
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(self._save); buttons.rejected.connect(self.reject)
        lay=QVBoxLayout(self); lay.addWidget(self.tabs); lay.addWidget(self.summary); lay.addWidget(buttons)
        self._load_general_and_rules(); self._update_summary()
        self._ensure_current_tab_loaded(self.tabs.currentIndex())

    def _build_general(self):
        page=QWidget(); form=QFormLayout(page)
        self.name=QLineEdit(); self.color=QLineEdit(); self.color_button=QPushButton("Farbe wählen"); self.color_button.clicked.connect(self._choose_color)
        color_row=QHBoxLayout(); color_row.addWidget(self.color); color_row.addWidget(self.color_button)
        self.description=QTextEdit(); self.description.setMaximumHeight(100)
        self.sort_order=QSpinBox(); self.sort_order.setRange(0,9999)
        self.active=QCheckBox("Aktiv"); self.default=QCheckBox("Standardgruppe")
        form.addRow("Name",self.name); form.addRow("Farbe",color_row); form.addRow("Beschreibung",self.description); form.addRow("Reihenfolge",self.sort_order); form.addRow("",self.active); form.addRow("",self.default)
        self.tabs.addTab(page,"Allgemein")

    def _build_assignment_tabs(self):
        self.assignment_tabs={}
        specs=[("vehicles","Fahrzeuge"),("trailers","Trailer"),("drivers","Fahrer"),("contractors","Unternehmer"),("users","Benutzer")]
        for key,title in specs:
            tab=AssignmentTab(title)
            tab.assignment_changed.connect(self._update_summary)
            self.assignment_tabs[key]=tab
            self.tabs.addTab(tab,title)

    def _build_rules(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        help_text = QLabel(
            "Regeln ordnen neue oder importierte Datensätze automatisch dieser Gruppe zu. "
            "Beispiel: Objekt „Fahrzeug“, Feld „Standort“, Operator „enthält“, Wert „Leipzig“. "
            "Die niedrigste Prioritätszahl wird zuerst geprüft; die erste passende Regel gewinnt."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("padding: 8px; background: #eef4fb; border: 1px solid #c8d8eb;")
        lay.addWidget(help_text)

        self.rules = QTableWidget(0, 6)
        self.rules.setHorizontalHeaderLabels(["Aktiv", "Priorität", "Objekt", "Feld", "Operator", "Vergleichswert"])
        self.rules.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rules.itemChanged.connect(self._update_rule_preview)
        lay.addWidget(self.rules)

        self.rule_preview = QLabel("Noch keine Regel angelegt.")
        self.rule_preview.setWordWrap(True)
        self.rule_preview.setStyleSheet("font-weight: bold; padding: 6px;")
        lay.addWidget(self.rule_preview)

        row = QHBoxLayout()
        add = QPushButton("Regel hinzufügen")
        add.clicked.connect(self._add_rule)
        delete = QPushButton("Regel entfernen")
        delete.clicked.connect(self._remove_rule)
        test = QPushButton("Regeln erklären")
        test.clicked.connect(self._test_rules)
        row.addWidget(add)
        row.addWidget(delete)
        row.addStretch()
        row.addWidget(test)
        lay.addLayout(row)
        self.tabs.addTab(page, "Regeln")

    def _load_general_and_rules(self):
        g = self.group
        self.name.setText(g.name or "")
        self.color.setText(g.color or "#4472C4")
        self.description.setPlainText(g.description or "")
        self.sort_order.setValue(g.sort_order or 100)
        self.active.setChecked(bool(g.active))
        self.default.setChecked(bool(getattr(g, "is_default", False)))
        for rule in g.rules:
            self._add_rule(rule)

    def _assignment_spec(self, key):
        g = self.group
        specs = {
            "vehicles": (
                Vehicle,
                select(Vehicle).order_by(Vehicle.vehicle_number, Vehicle.license_plate),
                {x.id for x in g.vehicles},
                lambda x: x.display_name,
            ),
            "trailers": (
                Trailer,
                select(Trailer).order_by(Trailer.trailer_number),
                {x.id for x in g.trailers},
                lambda x: x.display_name,
            ),
            "drivers": (
                Driver,
                select(Driver).order_by(Driver.last_name, Driver.first_name),
                {x.id for x in g.drivers},
                lambda x: f"{x.match_code} | {x.full_name}",
            ),
            "contractors": (
                Contractor,
                select(Contractor).order_by(Contractor.name, Contractor.match_code),
                {x.id for x in g.contractors},
                lambda x: x.display_name,
            ),
            "users": (
                User,
                select(User).order_by(User.username),
                {x.id for x in g.users},
                lambda x: f"{x.username} | {x.display_name}",
            ),
        }
        return specs[key]

    def _ensure_current_tab_loaded(self, index):
        # General is index 0; the five assignment tabs follow.
        keys = ("vehicles", "trailers", "drivers", "contractors", "users")
        assignment_index = index - 1
        if assignment_index < 0 or assignment_index >= len(keys):
            return
        key = keys[assignment_index]
        tab = self.assignment_tabs[key]
        if tab._loaded:
            return
        _model, statement, assigned_ids, label_fn = self._assignment_spec(key)
        tab.set_items(list(self.session.scalars(statement)), assigned_ids, label_fn)
        self._update_summary()

    def _choose_color(self):
        c=QColorDialog.getColor(QColor(self.color.text()),self); 
        if c.isValid(): self.color.setText(c.name())

    RULE_FIELDS = {
        "Fahrzeug": ["MatchCode", "Kennzeichen", "Fahrzeugart", "Einsatzart", "Standort"],
        "Trailer": ["MatchCode", "Kennzeichen", "Trailerart", "Standort"],
        "Fahrer": ["MatchCode", "Name", "Standort"],
        "Unternehmer": ["MatchCode", "Name", "Typ"],
    }
    RULE_OPERATORS = ["enthält", "ist gleich", "beginnt mit", "endet mit", "ist nicht gleich"]

    def _add_rule(self, rule=None):
        row = self.rules.rowCount()
        self.rules.insertRow(row)

        active = QTableWidgetItem()
        active.setFlags(active.flags() | Qt.ItemIsUserCheckable)
        active.setCheckState(Qt.Checked if rule is None or rule.active else Qt.Unchecked)
        self.rules.setItem(row, 0, active)

        priority = QTableWidgetItem(str(getattr(rule, "priority", 100)))
        self.rules.setItem(row, 1, priority)

        entity = QComboBox()
        entity.addItems(list(self.RULE_FIELDS))
        entity.setCurrentText(getattr(rule, "entity_type", "Fahrzeug"))
        entity.currentTextChanged.connect(lambda _text, r=row: self._rule_entity_changed(r))
        entity.currentTextChanged.connect(self._update_rule_preview)
        self.rules.setCellWidget(row, 2, entity)

        field = QComboBox()
        self.rules.setCellWidget(row, 3, field)

        operator = QComboBox()
        operator.addItems(self.RULE_OPERATORS)
        operator.setCurrentText(getattr(rule, "operator", "enthält"))
        operator.currentTextChanged.connect(self._update_rule_preview)
        self.rules.setCellWidget(row, 4, operator)

        value = QTableWidgetItem(getattr(rule, "comparison_value", ""))
        self.rules.setItem(row, 5, value)

        self._rule_entity_changed(row, getattr(rule, "field_name", "MatchCode"))
        self.rules.setCurrentCell(row, 5)
        self._update_rule_preview()

    def _rule_entity_changed(self, row, selected_field=None):
        entity = self.rules.cellWidget(row, 2)
        field = self.rules.cellWidget(row, 3)
        if not isinstance(entity, QComboBox) or not isinstance(field, QComboBox):
            return
        current = selected_field or field.currentText()
        field.blockSignals(True)
        field.clear()
        field.addItems(self.RULE_FIELDS.get(entity.currentText(), ["MatchCode"]))
        field.setCurrentText(current)
        field.blockSignals(False)
        try:
            field.currentTextChanged.disconnect(self._update_rule_preview)
        except (TypeError, RuntimeError):
            pass
        field.currentTextChanged.connect(self._update_rule_preview)
        self._update_rule_preview()

    def _rule_values(self, row):
        entity = self.rules.cellWidget(row, 2)
        field = self.rules.cellWidget(row, 3)
        operator = self.rules.cellWidget(row, 4)
        return {
            "active": self.rules.item(row, 0).checkState() == Qt.Checked,
            "priority": int((self.rules.item(row, 1).text() if self.rules.item(row, 1) else "100") or 100),
            "entity_type": entity.currentText() if isinstance(entity, QComboBox) else "Fahrzeug",
            "field_name": field.currentText() if isinstance(field, QComboBox) else "MatchCode",
            "operator": operator.currentText() if isinstance(operator, QComboBox) else "enthält",
            "comparison_value": (self.rules.item(row, 5).text() if self.rules.item(row, 5) else "").strip(),
        }

    def _remove_rule(self):
        rows = sorted({index.row() for index in self.rules.selectedIndexes()}, reverse=True)
        for row in rows:
            self.rules.removeRow(row)
        self._update_rule_preview()

    def _update_rule_preview(self, *_args):
        row = self.rules.currentRow()
        if row < 0 and self.rules.rowCount():
            row = 0
        if row < 0:
            self.rule_preview.setText("Noch keine Regel angelegt.")
            return
        values = self._rule_values(row)
        state = "Aktiv" if values["active"] else "Inaktiv"
        self.rule_preview.setText(
            f'{state}: Wenn bei einem {values["entity_type"]} das Feld „{values["field_name"]}“ '
            f'{values["operator"]} „{values["comparison_value"] or "…"}“, '
            f'wird es der Gruppe „{self.name.text() or "Neue Gruppe"}“ zugeordnet.'
        )

    def _test_rules(self):
        if not self.rules.rowCount():
            QMessageBox.information(self, "Regeln erklären", "Es ist noch keine Regel angelegt.")
            return
        explanations = []
        for row in range(self.rules.rowCount()):
            values = self._rule_values(row)
            if not values["active"]:
                continue
            explanations.append(
                f'{values["priority"]}: {values["entity_type"]}.{values["field_name"]} '
                f'{values["operator"]} „{values["comparison_value"] or "LEER"}“'
            )
        QMessageBox.information(
            self,
            "Regeln erklären",
            ("Aktive Regeln in Prüfreihenfolge:\n\n" + "\n".join(sorted(explanations)))
            if explanations else "Es gibt keine aktive Regel. Haken Sie mindestens eine Regel als aktiv an.",
        )

    def _update_summary(self):
        relation_names = ("vehicles", "trailers", "drivers", "contractors", "users")
        counts = []
        for key in relation_names:
            tab = self.assignment_tabs[key]
            counts.append(tab.assigned.count() if tab._loaded else len(getattr(self.group, key)))
        self.summary.setText(
            f"{self.name.text() or 'Neue Gruppe'} — {counts[0]} Fahrzeuge | {counts[1]} Trailer | "
            f"{counts[2]} Fahrer | {counts[3]} Unternehmer | {counts[4]} Benutzer | "
            f"{self.rules.rowCount()} Regeln"
        )

    def _save(self):
        if not self.name.text().strip(): QMessageBox.warning(self,"Pflichtfeld","Bitte einen Namen eingeben."); return
        g=self.group
        if g.id is None:self.session.add(g)
        if self.default.isChecked():
            for other in self.session.scalars(select(DispatchGroup).where(DispatchGroup.id != (g.id or -1))): other.is_default=False
        g.name=self.name.text().strip(); g.color=self.color.text().strip() or "#4472C4"; g.description=self.description.toPlainText().strip(); g.sort_order=self.sort_order.value(); g.active=self.active.isChecked(); g.is_default=self.default.isChecked()
        models={"vehicles":Vehicle,"trailers":Trailer,"drivers":Driver,"contractors":Contractor,"users":User}
        for key,model in models.items():
            tab = self.assignment_tabs[key]
            if not tab._loaded:
                continue
            ids = tab.assigned_ids()
            setattr(g,key,list(self.session.scalars(select(model).where(model.id.in_(ids)))) if ids else [])
        g.rules.clear()
        for row in range(self.rules.rowCount()):
            values = self._rule_values(row)
            g.rules.append(DispatchGroupRule(**values))
        self.session.commit(); self.accept()


class DispatchGroupDialog(QDialog):
    def __init__(self,session,parent=None):
        super().__init__(parent); self.session=session; self.setWindowTitle('Dispositionsgruppen'); self.resize(850,500)
        layout=QVBoxLayout(self); self.table=QTableWidget(0,8); self.table.setHorizontalHeaderLabels(['Name','Farbe','Fahrzeuge','Trailer','Fahrer','Unternehmer','Benutzer','Aktiv']); self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.table.doubleClicked.connect(self._edit); layout.addWidget(self.table)
        row=QHBoxLayout(); add=QPushButton('Gruppe anlegen'); add.clicked.connect(self._add); edit=QPushButton('Bearbeiten'); edit.clicked.connect(self._edit); delete=QPushButton('Löschen'); delete.clicked.connect(self._delete); row.addWidget(add); row.addWidget(edit); row.addWidget(delete); row.addStretch(); layout.addLayout(row); self.refresh()
    def refresh(self):
        self.items=list(self.session.scalars(select(DispatchGroup).order_by(DispatchGroup.sort_order,DispatchGroup.name))); self.table.setRowCount(len(self.items))
        for r,x in enumerate(self.items):
            vals=[x.name,x.color,str(len(x.vehicles)),str(len(x.trailers)),str(len(x.drivers)),str(len(x.contractors)),str(len(x.users)),'Ja' if x.active else 'Nein']
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(v))
        self.table.resizeColumnsToContents()
    def _selected(self):
        r=self.table.currentRow(); return self.items[r] if 0<=r<len(self.items) else None
    def _add(self):
        if GroupEditorDialog(self.session,parent=self).exec(): self.refresh()
    def _edit(self,*_):
        group=self._selected()
        if group and GroupEditorDialog(self.session,group,self).exec(): self.refresh()
    def _delete(self):
        group=self._selected()
        if group and QMessageBox.question(self,'Löschen',f'Dispositionsgruppe „{group.name}“ löschen?')==QMessageBox.Yes:
            self.session.delete(group); self.session.commit(); self.refresh()
