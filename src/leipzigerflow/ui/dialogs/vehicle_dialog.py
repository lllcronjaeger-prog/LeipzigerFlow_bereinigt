from PySide6.QtCore import QByteArray, QSettings
from PySide6.QtWidgets import QCheckBox,QDialog,QFileDialog,QHBoxLayout,QLabel,QLineEdit,QMessageBox,QPushButton,QTableView,QVBoxLayout
from leipzigerflow.database.session import SessionLocal
from leipzigerflow.imports.fleet_excel import export_rows,import_dicts,parse_date
from leipzigerflow.models.vehicle import Vehicle,VehicleClass,VehicleOwnership
from leipzigerflow.models.vehicle_staffing_profile import VehicleStaffingProfile
from leipzigerflow.services.driver_service import DriverService
from leipzigerflow.services.trailer_service import TrailerService
from leipzigerflow.services.vehicle_service import VehicleService
from leipzigerflow.services.location_service import LocationService
from leipzigerflow.ui.dialogs.vehicle_edit_dialog import VehicleEditDialog
from leipzigerflow.ui.models.vehicle_table_model import VehicleTableModel

class VehicleDialog(QDialog):
    preferred_workspace_size = (1400, 820)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Zugmaschinenverwaltung')
        self.setMinimumSize(1100,680)
        self.resize(*self.preferred_workspace_size)
        self._settings=QSettings('LeipzigerFlow','VehicleManagement')
        self.session=SessionLocal();self.service=VehicleService(self.session);self.trailer_service=TrailerService(self.session);self.driver_service=DriverService(self.session);self.location_service=LocationService(self.session);self.model=VehicleTableModel();self._build_ui();self._restore_view_state();self.refresh_table()
    def _build_ui(self):
        lay=QVBoxLayout(self);lay.addWidget(QLabel('<h2>Zugmaschinen</h2>'))
        f=QHBoxLayout();f.addWidget(QLabel('Suche:'));self.search=QLineEdit();self.search.setClearButtonEnabled(True);self.search.setPlaceholderText('Nummer, Kennzeichen, Art, Klasse, Standort oder Status');self.search.textChanged.connect(self.refresh_table);f.addWidget(self.search);self.show_archived=QCheckBox('Archivierte anzeigen');self.show_archived.toggled.connect(self.refresh_table);f.addWidget(self.show_archived);lay.addLayout(f)
        self.table=QTableView();self.table.setModel(self.model);self.table.setAlternatingRowColors(True);self.table.setSelectionBehavior(QTableView.SelectRows);self.table.setSelectionMode(QTableView.SingleSelection);self.table.setSortingEnabled(True);self.table.doubleClicked.connect(self.edit_vehicle);self.table.horizontalHeader().setStretchLastSection(True);lay.addWidget(self.table)
        row=QHBoxLayout()
        for text,fn in [('Neu',self.new_vehicle),('Bearbeiten',self.edit_vehicle),('Archivieren/Aktivieren',self.toggle_archive),('Excel importieren',self.import_excel),('Excel exportieren',self.export_excel)]:b=QPushButton(text);b.clicked.connect(fn);row.addWidget(b)
        row.addStretch();b=QPushButton('Schließen');b.clicked.connect(self.accept);row.addWidget(b);lay.addLayout(row)
    def _restore_view_state(self):
        state=self._settings.value('table_header')
        if isinstance(state,QByteArray) and not state.isEmpty():self.table.horizontalHeader().restoreState(state)
    def _save_view_state(self):
        self._settings.setValue('table_header',self.table.horizontalHeader().saveState());self._settings.sync()
    def _filtered(self):
        text=self.search.text().strip().lower();items=self.service.get_all()
        if not self.show_archived.isChecked():items=[v for v in items if v.active]
        if text:items=[v for v in items if text in ' '.join((v.vehicle_number,v.license_plate,getattr(v,'ownership_type',''),v.vehicle_class,v.location,v.status,v.remarks)).lower()]
        return items
    def refresh_table(self,*_):self.model.setVehicles(self._filtered())
    def selected_vehicle(self):
        rows=self.table.selectionModel().selectedRows();return self.model.vehicle_at(rows[0].row()) if rows else None
    def _available_trailers(self,current=None):
        coupled={v.trailer_id for v in self.service.get_all() if v.trailer_id and (current is None or v.id!=current.id)};return [t for t in self.trailer_service.get_all() if t.active and t.id not in coupled]
    def _drivers(self): return [d for d in self.driver_service.get_all() if d.active]
    def _locations(self): return [l for l in self.location_service.get_all() if l.active]
    def _save_profile(self, vehicle, data):
        profile=vehicle.staffing_profile
        if profile is None:
            profile=VehicleStaffingProfile(vehicle=vehicle)
            self.session.add(profile)
        for key,value in data.items():setattr(profile,key,value)
        self.session.commit()
    def new_vehicle(self):
        d=VehicleEditDialog(trailers=self._available_trailers(),drivers=self._drivers(),locations=self._locations(),parent=self)
        if d.exec()==QDialog.Accepted:
            try:
                v=Vehicle(**d.get_vehicle_data());self.service.add(v);self._save_profile(v,d.get_staffing_data());self.service.replace_absences(v,d.get_absence_drafts());self.refresh_table()
            except Exception as e:self.session.rollback();QMessageBox.critical(self,'Fehler',str(e))
    def edit_vehicle(self):
        v=self.selected_vehicle()
        if not v:return
        d=VehicleEditDialog(v,self._available_trailers(v),self._drivers(),self._locations(),self)
        if d.exec()==QDialog.Accepted:
            for k,val in d.get_vehicle_data().items():setattr(v,k,val)
            try:self.service.update(v);self._save_profile(v,d.get_staffing_data());self.service.replace_absences(v,d.get_absence_drafts());self.refresh_table()
            except Exception as e:self.session.rollback();QMessageBox.critical(self,'Fehler',str(e))
    def toggle_archive(self):
        v=self.selected_vehicle()
        if not v:return
        v.active=not v.active;self.service.update(v);self.refresh_table()
    def export_excel(self):
        path,_=QFileDialog.getSaveFileName(self,'Zugmaschinen exportieren','Zugmaschinen.xlsx','Excel (*.xlsx)')
        if not path:return
        items=self.service.get_all();export_rows(path,'Zugmaschinen',['Fahrzeugnummer','Kennzeichen','Fahrzeugart','Fahrzeugklasse','HU','Standort','Status','Bemerkung','Aktiv'],[[v.vehicle_number,v.license_plate,getattr(v,'ownership_type',VehicleOwnership.OWN.value),v.vehicle_class,v.hu_date,v.location,v.status,v.remarks,'Ja' if v.active else 'Nein'] for v in items]);QMessageBox.information(self,'Export','Export abgeschlossen.')
    def import_excel(self):
        path,_=QFileDialog.getOpenFileName(self,'Zugmaschinen importieren','','Excel (*.xlsx)')
        if not path:return
        count=0
        try:
            for r in import_dicts(path):
                plate=str(r.get('Kennzeichen') or '').strip().upper()
                if not plate:continue
                v=self.service.repository.get_by_license_plate(plate) or Vehicle(license_plate=plate)
                v.vehicle_number=str(r.get('Fahrzeugnummer') or plate);v.ownership_type=str(r.get('Fahrzeugart') or VehicleOwnership.OWN.value);v.vehicle_class=str(r.get('Fahrzeugklasse') or VehicleClass.STANDARD.value);v.hu_date=parse_date(r.get('HU'));v.location=str(r.get('Standort') or '');v.status=str(r.get('Status') or 'Frei');v.remarks=str(r.get('Bemerkung') or '');v.active=str(r.get('Aktiv') or 'Ja').lower() not in ('nein','0','false')
                self.service.update(v) if v.id else self.service.add(v);count+=1
            self.refresh_table();QMessageBox.information(self,'Import',f'{count} Zugmaschinen verarbeitet.')
        except Exception as e:QMessageBox.critical(self,'Importfehler',str(e))
    def accept(self):self._save_view_state();super().accept()
    def reject(self):self._save_view_state();super().reject()
    def closeEvent(self,e):self._save_view_state();self.session.close();super().closeEvent(e)
