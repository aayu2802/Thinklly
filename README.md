# ERP System - Setup Guide

A comprehensive ERP system for educational institutions built with Flask and MySQL.

## Prerequisites

- Python 3.8 or higher
- MySQL Server 5.7 or higher
- Git

## Installation & Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/edusaint/erp.git
cd erp
```

### Step 2: Configure Environment Variables

Create a `.env` file in the root directory of the project with the following content:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=YOUR_USERNAME
DB_PASS=YOUR_PASSWORD
DB_NAME=school_erp
```

**Important:** Replace `YOUR_USERNAME` and `YOUR_PASSWORD` with your actual MySQL credentials.

### Step 3: Set Up the Database

You have two options to import the database schema:

#### Option 1: Using MySQL Workbench (GUI)

1. Open MySQL Workbench
2. Connect to your MySQL server
3. Click on **Server** → **Data Import** in the top menu
4. Select **Import from Self-Contained File**
5. Browse and select the `migration.sql` file from the project directory
6. Under **Default Target Schema**, you can leave it empty or select `school_erp` (it will be created automatically)
7. Click **Start Import**
8. Wait for the import process to complete

**Note:** The migration file automatically creates the `school_erp` database, so you don't need to create it manually.

#### Option 2: Using Command Line

**For Windows (PowerShell):**
```powershell
Get-Content migration.sql | mysql -u YOUR_USERNAME -p
```

**For Linux/Mac:**
```bash
mysql -u YOUR_USERNAME -p < migration.sql
```

**Note:** You will be prompted to enter your MySQL password. The `migration.sql` file will automatically create the `school_erp` database if it doesn't exist.

### Step 4: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Run the Application

```bash
python main.py
```

The application will start on `http://127.0.0.1:5000`

## Default Login Credentials

### Admin Portal
**URL:** http://127.0.0.1:5000/admin/login

- **Username:** `admin`
- **Password:** `admin123`

### School Admin Portal
**URL:** http://127.0.0.1:5000/testschool/login

- **Username:** `schooladmin`
- **Password:** `admin123`

### Teacher Portal
**URL:** http://127.0.0.1:5000/testschool/teacher/login

- **Action:** Register a new teacher account
- Use the registration form to create your teacher credentials

## Project Structure

```
├── admin/                  # Admin module templates
├── akademi/               # Main application module
│   ├── routes.py         # Application routes
│   ├── static/           # Static assets (CSS, JS, images)
│   └── templates/        # HTML templates
├── migrations/            # Database migration scripts
├── scripts/              # Utility scripts
├── static/               # Global static files
├── config.py             # Configuration file
├── main.py               # Application entry point
├── models.py             # Database models
├── requirements.txt      # Python dependencies
└── migration.sql         # Database schema
```

## Troubleshooting

### Database Connection Issues
- Verify your MySQL server is running
- Check that the credentials in `.env` are correct
- Ensure the `school_erp` database exists

### Import Errors
- Make sure you're using a compatible Python version (3.8+)
- Try creating a virtual environment before installing dependencies:
  ```bash
  python -m venv venv
  venv\Scripts\activate  # Windows
  source venv/bin/activate  # Linux/Mac
  pip install -r requirements.txt
  ```

### Port Already in Use
- If port 5000 is already in use, you can modify the port in `main.py`

## Support

For issues and questions, please open an issue on the GitHub repository.

## License

[Add your license information here]
