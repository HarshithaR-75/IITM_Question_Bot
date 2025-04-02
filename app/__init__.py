from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_security import UserMixin, roles_required
from flask_login import LoginManager
from flask_migrate import Migrate

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres:root%40123@localhost/bot"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['USER_ENABLE_EMAIL'] = False  
app.config['SECRET_KEY'] = 'temp_key'  # Essential for session management (especially for login)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'routes.login'

# Import the User model after initializing db
from app.models import User
from app.routes import routes


# Register Blueprint after models and routes are loaded
app.register_blueprint(routes)
