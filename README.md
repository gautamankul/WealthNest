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


## Create a new user
1. Open a new shell 
```
python manage.py shell
```

2. Import the User model

```
from django.contrib.auth.models import User
```

3. Create a new user

```
user = User.objects.create_user( username='john_doe',email='john@example.com',password='securepassword123')
```

4. Optionally set additional fields
user.first_name = 'John'
user.last_name = 'Doe'

5. Save the user instance

```
user.save()
```