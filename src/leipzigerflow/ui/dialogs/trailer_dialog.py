from PySide6.QtWidgets import QCheckBox,QDialog,QFileDialog,QHBoxLayout,QLabel,QLineEdit,QMessageBox,QPushButton,QTableView,QVBoxLayout
from leipzigerflow.database.session import SessionLocal
from leipzigerflow.imports.fleet_excel import export_rows,import_dicts,parse_date
from leipzigerflow.models.trailer import Trailer,TrailerType
from leipzigerflow.services.trailer_service import TrailerService
from leipzigerflow.ui.dialogs.trailer_edit_dialog import TrailerEditDialog
from leipzigerflow.ui.models.trailer_table_model import TrailerTableModel
class TrailerDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle('Trailer-Übersicht');self.resize(1200,700);self.session=SessionLocal();self.service=TrailerService(self.session);self.model=TrailerTableModel();self._build();self.refresh()
    def _build(self):
        lay=QVBoxLayout(self);lay.addWidget(QLabel('<h2>Trailer</h2>'));f=QHBoxLayout();f.addWidget(QLabel('Suche:'));self.search=QLineEdit();self.search.setClearButtonEnabled(True);self.search.setPlaceholderText('Nummer, Kennzeichen, Typ, Standort oder Status');self.search.textChanged.connect(self.refresh);f.addWidget(self.search);self.show_archived=QCheckBox('Archivierte anzeigen');self.show_archived.toggled.connect(self.refresh);f.addWidget(self.show_archived);lay.addLayout(f)
        self.table=QTableView();self.table.setModel(self.model);self.table.setAlternatingRowColors(True);self.table.setSelectionBehavior(QTableView.SelectRows);self.table.setSelectionMode(QTableView.SingleSelection);self.table.setSortingEnabled(True);self.table.doubleClicked.connect(self.edit);self.table.horizontalHeader().setStretchLastSection(True);lay.addWidget(self.table)
        row=QHBoxLayout()
        for text,fn in [('Neu',self.new),('Bearbeiten',self.edit),('Archivieren/Aktivieren',self.toggle_archive),('Excel importieren',self.import_excel),('Excel exportieren',self.export_excel)]:b=QPushButton(text);b.clicked.connect(fn);row.addWidget(b)
        row.addStretch();b=QPushButton('Schließen');b.clicked.connect(self.accept);row.addWidget(b);lay.addLayout(row)
    def _filtered(self):
        text=self.search.text().strip().lower();items=self.service.get_all()
        if not self.show_archived.isChecked():items=[t for t in items if t.active]
        if text:items=[t for t in items if text in ' '.join((t.trailer_number,t.license_plate,t.trailer_type,t.location,t.status,t.remarks)).lower()]
        return items
    def refresh(self,*_):self.model.setTrailers(self._filtered())
    def selected(self):
        rows=self.table.selectionModel().selectedRows();return self.model.trailer_at(rows[0].row()) if rows else None
    def new(self):
        d=TrailerEditDialog(parent=self)
        if d.exec()==QDialog.Accepted:
            try:
                t=Trailer(**d.get_data());self.service.add(t);self.service.replace_absences(t,d.get_absence_drafts());self.refresh()
            except Exception as e:QMessageBox.critical(self,'Fehler',str(e))
    def edit(self):
        t=self.selected()
        if not t:return
        d=TrailerEditDialog(t,self)
        if d.exec()==QDialog.Accepted:
            for k,v in d.get_data().items():setattr(t,k,v)
            try:self.service.update(t);self.service.replace_absences(t,d.get_absence_drafts());self.refresh()
            except Exception as e:QMessageBox.critical(self,'Fehler',str(e))
    def toggle_archive(self):
        t=self.selected()
        if not t:return
        t.active=not t.active;self.service.update(t);self.refresh()
    def export_excel(self):
        path,_=QFileDialog.getSaveFileName(self,'Trailer exportieren','Trailer.xlsx','Excel (*.xlsx)')
        if not path:return
        items=self.service.get_all();export_rows(path,'Trailer',['Trailernummer','Kennzeichen','Trailertyp','HU','SP','Standort','Status','Bemerkung','Aktiv'],[[t.trailer_number,t.license_plate,t.trailer_type,t.hu_date,t.sp_date,t.location,t.status,t.remarks,'Ja' if t.active else 'Nein'] for t in items]);QMessageBox.information(self,'Export','Export abgeschlossen.')
    def import_excel(self):
        path,_=QFileDialog.getOpenFileName(self,'Trailer importieren','','Excel (*.xlsx)')
        if not path:return
        count=0
        try:
            for r in import_dicts(path):
                number=str(r.get('Trailernummer') or '').strip().upper();plate=str(r.get('Kennzeichen') or '').strip().upper()
                if not number or not plate:continue
                t=self.service.repository.get_by_number(number) or Trailer(trailer_number=number,license_plate=plate,trailer_type=TrailerType.PLANE.value)
                t.license_plate=plate;t.trailer_type=str(r.get('Trailertyp') or TrailerType.PLANE.value);t.hu_date=parse_date(r.get('HU'));t.sp_date=parse_date(r.get('SP'));t.location=str(r.get('Standort') or '');t.status=str(r.get('Status') or 'Frei');t.remarks=str(r.get('Bemerkung') or '');t.active=str(r.get('Aktiv') or 'Ja').lower() not in ('nein','0','false')
                self.service.update(t) if t.id else self.service.add(t);count+=1
            self.refresh();QMessageBox.information(self,'Import',f'{count} Trailer verarbeitet.')
        except Exception as e:QMessageBox.critical(self,'Importfehler',str(e))
    def closeEvent(self,e):self.session.close();super().closeEvent(e)
