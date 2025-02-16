from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Initialize Flask app

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres:root%40123@localhost/bot"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# Move import after app and db initialization
from app.routes import routes

# Register Blueprint
app.register_blueprint(routes)
