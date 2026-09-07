from django.db import migrations
SQL='''
CREATE OR REPLACE FUNCTION nexo_reject_history_change() RETURNS trigger AS $$
BEGIN
 RAISE EXCEPTION 'Nexo: posted history is immutable; use a compensating operation';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER nexo_stock_history BEFORE UPDATE OR DELETE ON core_stockmovement FOR EACH ROW EXECUTE FUNCTION nexo_reject_history_change();
CREATE TRIGGER nexo_audit_history BEFORE UPDATE OR DELETE ON core_audit FOR EACH ROW EXECUTE FUNCTION nexo_reject_history_change();
CREATE TRIGGER nexo_invoice_history BEFORE UPDATE OR DELETE ON core_invoice FOR EACH ROW EXECUTE FUNCTION nexo_reject_history_change();
CREATE TRIGGER nexo_lines_history BEFORE UPDATE OR DELETE ON core_documentline FOR EACH ROW EXECUTE FUNCTION nexo_reject_history_change();
'''
REVERSE='''
DROP TRIGGER nexo_stock_history ON core_stockmovement;
DROP TRIGGER nexo_audit_history ON core_audit;
DROP TRIGGER nexo_invoice_history ON core_invoice;
DROP TRIGGER nexo_lines_history ON core_documentline;
DROP FUNCTION nexo_reject_history_change();
'''
class Migration(migrations.Migration):
    dependencies=[('core','0001_initial')]
    operations=[migrations.RunSQL(SQL,REVERSE)]
