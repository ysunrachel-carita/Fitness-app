import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import unittest
from datetime import datetime, timedelta
from core.insights import weekly_volume_spike, recovery_flags, pr_staleness

class TestInsights(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        
        # Create minimal schema
        self.conn.executescript('''
            CREATE TABLE users (id INTEGER PRIMARY KEY);
            CREATE TABLE exercises (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE exercise_sessions (id INTEGER PRIMARY KEY, user_id INTEGER, exercise_id INTEGER, date TEXT);
            CREATE TABLE set_entries (id INTEGER PRIMARY KEY, session_id INTEGER, weight_kg REAL, reps INTEGER, rpe REAL);
            CREATE TABLE runs (id INTEGER PRIMARY KEY, user_id INTEGER, distance_km REAL, date TEXT);
            CREATE TABLE wods (id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT);
        ''')
        
        self.user_id = 1
        self.conn.execute('INSERT INTO users (id) VALUES (?)', (self.user_id,))
        self.conn.execute('INSERT INTO exercises (id, name) VALUES (1, "Squat")')
        
        self.today = datetime.now()

    def tearDown(self):
        self.conn.close()

    def test_weekly_volume_spike(self):
        # Insert prev week data (100 kg lifts, 10 km run, 1 WOD)
        prev_date = (self.today - timedelta(days=10)).strftime("%Y-%m-%d")
        self.conn.execute('INSERT INTO exercise_sessions (id, user_id, exercise_id, date) VALUES (1, ?, 1, ?)', (self.user_id, prev_date))
        self.conn.execute('INSERT INTO set_entries (session_id, weight_kg, reps) VALUES (1, 10, 10)')
        
        self.conn.execute('INSERT INTO runs (user_id, distance_km, date) VALUES (?, 10, ?)', (self.user_id, prev_date))
        self.conn.execute('INSERT INTO wods (user_id, date) VALUES (?, ?)', (self.user_id, prev_date))

        # Insert cur week data (200 kg lifts - 100% spike, 11 km run - 10% spike, 2 WODs - 100% spike)
        cur_date = (self.today - timedelta(days=2)).strftime("%Y-%m-%d")
        self.conn.execute('INSERT INTO exercise_sessions (id, user_id, exercise_id, date) VALUES (2, ?, 1, ?)', (self.user_id, cur_date))
        self.conn.execute('INSERT INTO set_entries (session_id, weight_kg, reps) VALUES (2, 20, 10)')
        
        self.conn.execute('INSERT INTO runs (user_id, distance_km, date) VALUES (?, 11.5, ?)', (self.user_id, cur_date))
        self.conn.execute('INSERT INTO wods (user_id, date) VALUES (?, ?)', (self.user_id, cur_date))
        self.conn.execute('INSERT INTO wods (user_id, date) VALUES (?, ?)', (self.user_id, cur_date))

        res = weekly_volume_spike(self.user_id, conn=self.conn)
        self.assertTrue(res['flag'])
        self.assertEqual(res['severity'], 'alert')
        self.assertIn('Lifting volume increased by 100%', res['message'])
        self.assertIn('Running volume increased by 15%', res['message'])
        self.assertIn('WOD volume increased by 100%', res['message'])

    def test_recovery_flags_consecutive_hi(self):
        # Insert high intensity on consecutive days
        d1 = (self.today - timedelta(days=3)).strftime("%Y-%m-%d")
        d2 = (self.today - timedelta(days=2)).strftime("%Y-%m-%d")
        
        self.conn.execute('INSERT INTO exercise_sessions (id, user_id, exercise_id, date) VALUES (1, ?, 1, ?)', (self.user_id, d1))
        self.conn.execute('INSERT INTO set_entries (session_id, weight_kg, reps, rpe) VALUES (1, 100, 1, 9)')
        
        self.conn.execute('INSERT INTO wods (user_id, date) VALUES (?, ?)', (self.user_id, d2))
        
        res = recovery_flags(self.user_id, conn=self.conn)
        self.assertTrue(res['flag'])
        self.assertEqual(res['severity'], 'alert')
        self.assertIn('consecutive days', res['message'])

    def test_recovery_flags_overtraining(self):
        # Train 6 out of 7 days
        for i in range(1, 7):
            d = (self.today - timedelta(days=i)).strftime("%Y-%m-%d")
            self.conn.execute('INSERT INTO runs (user_id, distance_km, date) VALUES (?, 5, ?)', (self.user_id, d))
            
        res = recovery_flags(self.user_id, conn=self.conn)
        self.assertTrue(res['flag'])
        self.assertEqual(res['severity'], 'warning')
        self.assertIn('6 days', res['message'])

    def test_pr_staleness(self):
        # Make Squat a frequent lift (8 sessions in last 56 days)
        for i in range(8):
            d = (self.today - timedelta(days=20 + i)).strftime("%Y-%m-%d")
            sess_id = i + 10
            self.conn.execute('INSERT INTO exercise_sessions (id, user_id, exercise_id, date) VALUES (?, ?, 1, ?)', (sess_id, self.user_id, d))
            self.conn.execute('INSERT INTO set_entries (session_id, weight_kg, reps) VALUES (?, 50, 5)', (sess_id,))
            
        # Insert a PR 65 days ago
        old_pr_date = (self.today - timedelta(days=65)).strftime("%Y-%m-%d")
        self.conn.execute('INSERT INTO exercise_sessions (id, user_id, exercise_id, date) VALUES (99, ?, 1, ?)', (self.user_id, old_pr_date))
        self.conn.execute('INSERT INTO set_entries (session_id, weight_kg, reps) VALUES (99, 100, 1)')
        
        res = pr_staleness(self.user_id, conn=self.conn)
        self.assertTrue(res['flag'])
        self.assertEqual(res['severity'], 'warning')
        self.assertIn('Squat', res['message'])

if __name__ == '__main__':
    unittest.main()
