# FILE: run.py
from app import create_app

app = create_app()

if __name__ == '__main__':
    print("To create your first admin user, run this command in your terminal:")
    print("python create_admin.py")
    app.run(debug=True)