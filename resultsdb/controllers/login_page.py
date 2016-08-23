# Copyright 2013, Red Hat, Inc
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Authors:
#   Josef Skladanka <jskladan@redhat.com>

from flask import Blueprint, render_template, redirect, flash, url_for, request
from flask.ext.wtf import Form
from wtforms import TextField, PasswordField, HiddenField
from wtforms.validators import Required
from flask.ext.login import login_user, logout_user, login_required, current_user, AnonymousUserMixin


from resultsdb import app, login_manager
from resultsdb.models.user import User

login_page = Blueprint('login_page', __name__)


class LoginForm(Form):
    username = TextField(u'Username', validators=[Required()])
    password = PasswordField(u'Password', validators=[Required()])
    next_page = HiddenField()


# handle login stuff
@login_manager.user_loader
def load_user(userid):
    user = User.query.get(userid)
    if user:
        return user
    else:
        return AnonymousUserMixin


@login_page.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm()

    if login_form.validate_on_submit():
        user = User.query.filter_by(username=login_form.username.data).first()
        if user and user.check_password(login_form.password.data):
            login_user(user)

            app.logger.info('Successful login for user %s' % login_form.username.data)
            flash('Logged In Successfully!')

            return redirect(login_form.next_page.data)
        else:
            app.logger.info('FAILED login for user %s' % login_form.username.data)
            flash('Login Failed! Please Try again!')

    login_form.next_page.data = request.args.get('next') or url_for('main.index')
    return render_template('login.html', form=login_form)


@login_page.route('/logout')
@login_required
def logout():
    app.logger.info('logout for user %s' % current_user.username)
    logout_user()
    flash('Logged Out Successfully!')
    return redirect(url_for('main.index'))
