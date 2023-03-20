import sys
import subprocess
from datetime import datetime, timedelta, time
from os import name

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt5.QtCore import QTimer, pyqtSignal, pyqtSlot
import sqlite3
from rumps import rumps


def init_db():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (name TEXT, user_number TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS last_user (name TEXT, user_number TEXT)")
    conn.commit()
    conn.close()


def get_last_logged_user():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM last_user")
    user = cur.fetchone()
    conn.close()
    return user


def update_last_logged_user(name, user_number):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM last_user")
    cur.execute("INSERT INTO last_user VALUES (?, ?)", (name, user_number))
    conn.commit()
    conn.close()


class LoginWindow(QWidget):
    login_signal = pyqtSignal(str, str)

    def __init__(self, time_tracker_app):
        super().__init__()
        self.time_tracker_app = time_tracker_app
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Time Tracker Login')
        self.layout = QVBoxLayout()

        self.name_label = QLabel('Name:')
        self.layout.addWidget(self.name_label)

        self.name_input = QLineEdit()
        self.layout.addWidget(self.name_input)

        self.user_number_label = QLabel('User Number:')
        self.layout.addWidget(self.user_number_label)

        self.user_number_input = QLineEdit()
        self.layout.addWidget(self.user_number_input)

        self.login_button = QPushButton('Login')
        self.login_button.clicked.connect(self.handle_login)
        self.layout.addWidget(self.login_button)

        self.create_user_button = QPushButton('Create User')
        self.create_user_button.clicked.connect(self.create_user)
        self.layout.addWidget(self.create_user_button)

        self.setLayout(self.layout)

    def handle_login(self):
        name = self.name_input.text()
        user_number = self.user_number_input.text()

        if name and user_number:
            self.login_signal.emit(name, user_number)
            self.close()

    def create_user(self):
        name = self.name_input.text()
        user_number = self.user_number_input.text()

        if name and user_number:
            update_last_logged_user(name, user_number)
            self.login_signal.emit(name, user_number)
            self.close()


class LunchReminderWindow(QWidget):
    set_lunch_reminder_signal = pyqtSignal(int, int)

    def __init__(self, time_tracker_app):
        super().__init__()
        self.time_tracker_app = time_tracker_app
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Lunch Reminder')
        self.layout = QVBoxLayout()

        self.time_label = QLabel('Lunch Time (HH:MM):')
        self.layout.addWidget(self.time_label)

        self.time_input = QLineEdit()
        self.layout.addWidget(self.time_input)

        self.set_button = QPushButton('Set Reminder')
        self.set_button.clicked.connect(self.set_lunch_reminder)
        self.layout.addWidget(self.set_button)

        self.setLayout(self.layout)

    def set_lunch_reminder(self):
        lunch_time = self.time_input.text()
        try:
            hour, minute = map(int, lunch_time.split(':'))
            self.set_lunch_reminder_signal.emit(hour, minute)
            self.close()
        except ValueError:
            QMessageBox.warning(self, "Invalid Time", "Please enter a valid time in the format HH:MM.")


class TimeTrackerApp(rumps.App):
    def init(self):
        super().init("Time Tracker", icon="icon.png")
        self.logged_in = False
        self.login_window = None
        self.worked_time_window = None
        self.monthly_worked_hours = 0
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_timer)
        self.login_window_signal = LoginWindow.login_signal
        self.login_window_signal.connect(self.set_user_info)

        self.lunch_reminder_window_signal = LunchReminderWindow.set_lunch_reminder_signal
        self.lunch_reminder_window_signal.connect(self.set_lunch_reminder)

        self.login_item = rumps.MenuItem(title="Login", callback=self.show_login)
        self.logout_item = rumps.MenuItem(title="Logout", callback=self.logout)
        self.change_user_item = rumps.MenuItem(title="Change User", callback=self.show_login)
        self.set_lunch_reminder_item = rumps.MenuItem(title="Set Lunch Reminder", callback=self.show_lunch_reminder)
        self.menu = [self.login_item, self.logout_item, self.change_user_item, self.set_lunch_reminder_item]

        if get_last_logged_user() is not None:
            self.set_user_info(*get_last_logged_user())

    @pyqtSlot(str, str)
    def set_user_info(self, name, user_number):
        self.logged_in = True
        self.current_user = f"{name} ({user_number})"
        update_last_logged_user(name, user_number)
        self.start_time = datetime.now()
        self.timer.start()

    @rumps.clicked("Time Tracker")
    def icon_clicked(self, _):
        if self.logged_in:
            elapsed_time = datetime.now() - self.start_time
            time_worked_today = str(elapsed_time).split('.')[0]
            rumps.alert(title="Time Tracker",
                        message=f"Time Worked Today: {time_worked_today}\nCurrent User: {self.current_user}")
        else:
            self.show_login()

    def show_login(self, _=None):
        if not self.login_window:
            self.login_window = LoginWindow(self)
        self.login_window.show()

    def logout(self):
        self.logged_in = False
        self.timer.stop()
        elapsed_time = datetime.now() - self.start_time
        self.monthly_worked_hours += elapsed_time.total_seconds() / 3600
        rumps.notification("Time Tracker", "Logged out",
                           f"Goodbye! Monthly worked hours: {self.monthly_worked_hours:.2f}")

    def show_lunch_reminder(self, _):
        if not self.lunch_reminder_window:
            self.lunch_reminder_window = LunchReminderWindow(self)
        self.lunch_reminder_window.show()

    @pyqtSlot(int, int)
    def set_lunch_reminder(self, hour, minute):
        self.lunch_reminder_time = time(hour, minute)
        rumps.notification("Time Tracker", "Lunch Reminder Set", f"Lunch reminder set for {hour}:{minute:02d}")

    def update_timer(self):
        now = datetime.now()
        elapsed_time = now - self.start_time
        end_of_day = datetime.combine(now.date(), time(17, 30))
        remaining_time = end_of_day - now

        if remaining_time <= timedelta(0):
            remaining_time = timedelta(0)

        if now.time() == self.lunch_reminder_time:
            subprocess.call(["afplay[/System/Library/Sounds/Ping.aiff"])


if name == 'main':
    app = QApplication(sys.argv)
    time_tracker_app = TimeTrackerApp()
    time_tracker_app.run()
