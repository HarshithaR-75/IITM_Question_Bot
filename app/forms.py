from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField
from wtforms.validators import DataRequired, Length, EqualTo

# ✅ Registration Form (Includes Role Selection)
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[('Admin', 'Admin'), ('Student', 'Student')], validators=[DataRequired()])
    submit = SubmitField('Register')

# ✅ Login Form (Handles Admin and Student Login Separately)
class LoginForm(FlaskForm): 
    student_id = StringField('Student ID')  # Only for Students
    username = StringField('Username')  # Only for Admins
    password = PasswordField('Password', validators=[DataRequired()])
    role = SelectField('Role', choices=[('Admin', 'Admin'), ('Student', 'Student')], validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')
