PR-011.4.1 – SQLAlchemy-Lagerbeziehung Bugfix

Ursache:
PR-011.4 hatte location.py und schema_migrations.py mit einem Stand ohne warehouse_group_id überschrieben. Dadurch konnte SQLAlchemy die Beziehung WarehouseGroup.locations nicht konfigurieren und 39 Tests fielen als Folgefehler aus.

Geändert:
- Location besitzt wieder warehouse_group_id mit ForeignKey auf warehouse_groups.id.
- Beziehung Location.warehouse_group ist wieder vorhanden.
- Kundenstandorte verwenden weiterhin customer_id.
- Dispositionsimport verwendet customer_id statt des alten owner_customer_id.
- Schema-Migration enthält Kundenstandorte, Lagergruppen und Zeitfenster-Historie gemeinsam.

Testergebnis: 187 passed.
