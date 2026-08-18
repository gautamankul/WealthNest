# Revised Investment Dashboard

This version turns the original dashboard into a monthly investment tracker with:

- Monthly contribution entry by Mutual Funds, Gold, Silver, Bonds and Other.
- Permanent monthly history stored in SQLite/Django.
- Current allocation vs user-defined target allocation.
- Automatic allocation gap calculation.
- Suggested next-month allocation based on target percentages.
- Portfolio investment/current value/profit/return summary.
- Monthly investment trend chart.
- Goals and simple projections.
- Reports page with custom date range, contribution table, chart and CSV export.

## Run

python -m venv venv

Windows:
venv\\Scripts\\activate

macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

Open http://127.0.0.1:8000/

The first dashboard load seeds the example values from the supplied dashboard, including the portfolio holdings, target allocation and sample monthly contribution history. Replace them with your own data using the dashboard.

Admin: http://127.0.0.1:8000/admin/
