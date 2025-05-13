# chore_chart_project/app.py

from flask import Flask, request, jsonify, render_template, g
import sqlite3
import os
from datetime import date # Use date for date comparisons

# --- App Configuration ---
app = Flask(__name__)
DATABASE = 'chore_chart.db'
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'supersecret') # Add -e ADMIN_PASSWORD="your_strong_password" with docker run to not use the default
BALLOONS_PER_STAR = 10 # Make this configurable if needed later

# --- Database Setup & Helpers ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    db = get_db()
    cur = db.cursor()
    cur.execute(query, args)
    db.commit()
    last_row_id = cur.lastrowid
    cur.close()
    return last_row_id

# --- Schema (Updated) ---
SCHEMA_SQL = """
DROP TABLE IF EXISTS kids;
CREATE TABLE kids (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    avatar_color TEXT,
    balloons INTEGER DEFAULT 0,
    train_track_length INTEGER DEFAULT 10,
    train_laps_completed INTEGER DEFAULT 0
);

DROP TABLE IF EXISTS chores_master;
CREATE TABLE chores_master (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    icon TEXT
);

DROP TABLE IF EXISTS chore_assignments;
CREATE TABLE chore_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kid_id INTEGER,
    chore_id INTEGER,
    frequency TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (kid_id) REFERENCES kids (id) ON DELETE CASCADE,
    FOREIGN KEY (chore_id) REFERENCES chores_master (id) ON DELETE CASCADE
);

DROP TABLE IF EXISTS chore_completions;
CREATE TABLE chore_completions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER,
    kid_id INTEGER NOT NULL,
    chore_id INTEGER NOT NULL,
    date_completed TEXT NOT NULL, -- YYYY-MM-DD
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (kid_id) REFERENCES kids (id) ON DELETE CASCADE,
    FOREIGN KEY (chore_id) REFERENCES chores_master (id) ON DELETE CASCADE,
    FOREIGN KEY (assignment_id) REFERENCES chore_assignments (id) ON DELETE SET NULL
);

DROP TABLE IF EXISTS stars;
CREATE TABLE stars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kid_id INTEGER NOT NULL,
    date_awarded TEXT NOT NULL, -- YYYY-MM-DD
    type TEXT NOT NULL, -- 'daily', 'bonus', 'balloon_conversion'
    reason TEXT,
    FOREIGN KEY (kid_id) REFERENCES kids (id) ON DELETE CASCADE
);
"""
# --- Admin Authentication ---
def check_admin_auth():
    auth_password = request.headers.get('X-Admin-Password')
    return auth_password == ADMIN_PASSWORD

# --- Helper: Update Train Laps ---
def update_train_laps(kid_id):
    kid_info = query_db("SELECT train_track_length FROM kids WHERE id = ?", (kid_id,), one=True)
    if not kid_info or kid_info['train_track_length'] <= 0:
        return

    stars_count_data = query_db("SELECT COUNT(id) as count FROM stars WHERE kid_id = ?", (kid_id,), one=True)
    total_stars = stars_count_data['count'] if stars_count_data else 0
    
    new_laps = total_stars // kid_info['train_track_length']
    execute_db("UPDATE kids SET train_laps_completed = ? WHERE id = ?", (new_laps, kid_id))


# --- API Endpoints ---
@app.route('/')
def index():
    return render_template('index.html')

# --- Kids API (Updated) ---
@app.route('/api/kids', methods=['GET'])
def get_kids():
    kids_data = query_db("""
        SELECT k.id, k.name, k.avatar_color, k.balloons, k.train_track_length, k.train_laps_completed, COUNT(s.id) as stars_count
        FROM kids k
        LEFT JOIN stars s ON k.id = s.kid_id
        GROUP BY k.id
    """)
    return jsonify([dict(row) for row in kids_data])

@app.route('/api/kids', methods=['POST'])
def add_kid():
    if not check_admin_auth(): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    name = data.get('name')
    avatar_color = data.get('avatarColor')
    track_length = data.get('trainTrackLength', 10) # Default to 10 if not provided
    if not name: return jsonify({"error": "Kid name is required"}), 400
    
    kid_id = execute_db("INSERT INTO kids (name, avatar_color, balloons, train_track_length, train_laps_completed) VALUES (?, ?, 0, ?, 0)", 
                        (name, avatar_color, track_length))
    return jsonify({"id": kid_id, "name": name, "avatarColor": avatar_color, "balloons": 0, "stars_count": 0, "train_track_length": track_length, "train_laps_completed": 0}), 201

# --- Master Chores & Assignments API (Mostly Unchanged, ensure they exist) ---
@app.route('/api/chores-master', methods=['GET'])
def get_master_chores():
    chores_data = query_db("SELECT * FROM chores_master")
    return jsonify([dict(row) for row in chores_data])

@app.route('/api/chores-master', methods=['POST'])
def add_master_chore():
    if not check_admin_auth(): return jsonify({"error": "Unauthorized"}), 401
    data = request.json; name = data.get('name'); icon = data.get('icon')
    if not name: return jsonify({"error": "Chore name is required"}), 400
    chore_id = execute_db("INSERT INTO chores_master (name, icon) VALUES (?, ?)", (name, icon))
    return jsonify({"id": chore_id, "name": name, "icon": icon}), 201

@app.route('/api/assignments', methods=['GET'])
def get_assignments():
    kid_id_filter = request.args.get('kid_id')
    sql = """
        SELECT ca.id, ca.kid_id, k.name as kid_name, ca.chore_id, cm.name as chore_name, cm.icon as chore_icon, ca.frequency
        FROM chore_assignments ca JOIN kids k ON ca.kid_id = k.id JOIN chores_master cm ON ca.chore_id = cm.id
    """
    params = []
    if kid_id_filter: sql += " WHERE ca.kid_id = ?"; params.append(kid_id_filter)
    assignments_data = query_db(sql, params)
    return jsonify([dict(row) for row in assignments_data])

@app.route('/api/assignments', methods=['POST'])
def add_assignment():
    if not check_admin_auth(): return jsonify({"error": "Unauthorized"}), 401
    data = request.json; kid_id_input = data.get('kidId'); chore_id = data.get('choreId'); frequency = data.get('frequency')
    if not chore_id or not frequency: return jsonify({"error": "Chore ID and frequency are required"}), 400
    assigned_ids = []; kids_to_assign = []
    if kid_id_input == 'all':
        all_kids_data = query_db("SELECT id FROM kids"); kids_to_assign = [k['id'] for k in all_kids_data]
    elif kid_id_input:
        try: kids_to_assign.append(int(kid_id_input))
        except ValueError: return jsonify({"error": "Invalid Kid ID"}), 400
    else: return jsonify({"error": "Kid ID ('all' or specific) is required"}), 400
    if not kids_to_assign: return jsonify({"error": "No kids found to assign chores to."}), 400
    for k_id in kids_to_assign:
        existing = query_db("SELECT id FROM chore_assignments WHERE kid_id = ? AND chore_id = ? AND frequency = ?", (k_id, chore_id, frequency), one=True)
        if not existing:
            assignment_id = execute_db("INSERT INTO chore_assignments (kid_id, chore_id, frequency) VALUES (?, ?, ?)", (k_id, chore_id, frequency))
            assigned_ids.append(assignment_id)
    if not assigned_ids: return jsonify({"message": "Chores already assigned or no new assignments made."}), 200
    return jsonify({"message": "Chore(s) assigned successfully", "assignment_ids": assigned_ids}), 201

@app.route('/api/assignments/<int:assignment_id>', methods=['DELETE'])
def delete_assignment(assignment_id):
    if not check_admin_auth(): return jsonify({"error": "Unauthorized"}), 401
    execute_db("DELETE FROM chore_assignments WHERE id = ?", (assignment_id,))
    return jsonify({"message": "Assignment removed"}), 200

# --- Chore Completions & Rewards API (Updated) ---
def get_chores_for_kid_today_internal(kid_id, today_date_obj):
    today_date_str = today_date_obj.isoformat()
    day_of_week_idx = today_date_obj.weekday()
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    current_day_name = day_names[day_of_week_idx]
    assigned_chores_sql = """
        SELECT ca.id as assignment_id, ca.kid_id, ca.chore_id, cm.name as chore_name, cm.icon as chore_icon, ca.frequency
        FROM chore_assignments ca JOIN chores_master cm ON ca.chore_id = cm.id
        WHERE ca.kid_id = ? AND ca.is_active = 1
    """
    all_kid_assignments = query_db(assigned_chores_sql, (kid_id,))
    chores_due_today = []
    for assignment in all_kid_assignments:
        assignment_dict = dict(assignment); is_due = False
        if assignment_dict['frequency'] == 'daily': is_due = True
        elif assignment_dict['frequency'] == 'weekdays' and 0 <= day_of_week_idx <= 4: is_due = True
        elif assignment_dict['frequency'] == 'weekends' and 5 <= day_of_week_idx <= 6: is_due = True
        elif assignment_dict['frequency'] == current_day_name: is_due = True
        if is_due:
            completion = query_db("SELECT id FROM chore_completions WHERE assignment_id = ? AND kid_id = ? AND date_completed = ?",
                                  (assignment_dict['assignment_id'], kid_id, today_date_str), one=True)
            assignment_dict['completed_today'] = True if completion else False
            chores_due_today.append(assignment_dict)
    return chores_due_today

@app.route('/api/kids/<int:kid_id>/chores-today', methods=['GET'])
def get_kid_chores_today_api(kid_id):
    chores = get_chores_for_kid_today_internal(kid_id, date.today())
    kid_info = query_db("SELECT k.id, k.name, k.avatar_color, k.balloons, k.train_track_length, k.train_laps_completed, COUNT(s.id) as stars_count FROM kids k LEFT JOIN stars s ON k.id = s.kid_id WHERE k.id = ? GROUP BY k.id", (kid_id,), one=True)
    if not kid_info: return jsonify({"error": "Kid not found"}), 404
    return jsonify({"kid_info": dict(kid_info), "chores": chores})

@app.route('/api/completions', methods=['POST']) # Mark chore complete
def mark_chore_complete():
    data = request.json; kid_id = data.get('kidId'); assignment_id = data.get('assignmentId'); chore_id = data.get('choreId')
    today_date_obj = date.today(); today_date_str = today_date_obj.isoformat()
    if not kid_id or not chore_id or not assignment_id: return jsonify({"error": "Kid ID, Chore ID, and Assignment ID are required"}), 400
    
    existing_completion = query_db("SELECT id FROM chore_completions WHERE assignment_id = ? AND kid_id = ? AND date_completed = ?", (assignment_id, kid_id, today_date_str), one=True)
    if existing_completion: return jsonify({"message": "Chore already marked as complete for today."}), 200

    execute_db("INSERT INTO chore_completions (assignment_id, kid_id, chore_id, date_completed) VALUES (?, ?, ?, ?)", (assignment_id, kid_id, chore_id, today_date_str))
    execute_db("UPDATE kids SET balloons = balloons + 1 WHERE id = ?", (kid_id,))
    
    kid_data = query_db("SELECT balloons FROM kids WHERE id = ?", (kid_id,), one=True)
    balloons_after_award = kid_data['balloons']; stars_from_balloons = 0
    if balloons_after_award >= BALLOONS_PER_STAR:
        stars_from_balloons = balloons_after_award // BALLOONS_PER_STAR
        remaining_balloons = balloons_after_award % BALLOONS_PER_STAR
        execute_db("UPDATE kids SET balloons = ? WHERE id = ?", (remaining_balloons, kid_id,))
        for _ in range(stars_from_balloons):
            execute_db("INSERT INTO stars (kid_id, date_awarded, type, reason) VALUES (?, ?, 'balloon_conversion', ? || ' balloons earned')", (kid_id, today_date_str, BALLOONS_PER_STAR))
            update_train_laps(kid_id) # Update laps after star award
    
    daily_star_awarded_this_action = False
    chores_due_today = get_chores_for_kid_today_internal(kid_id, today_date_obj)
    if chores_due_today:
        all_done = all(c['completed_today'] for c in chores_due_today)
        if all_done:
            daily_star_exists = query_db("SELECT id FROM stars WHERE kid_id = ? AND date_awarded = ? AND type = 'daily'", (kid_id, today_date_str), one=True)
            if not daily_star_exists:
                execute_db("INSERT INTO stars (kid_id, date_awarded, type, reason) VALUES (?, ?, 'daily', 'All daily chores completed')", (kid_id, today_date_str))
                daily_star_awarded_this_action = True
                update_train_laps(kid_id) # Update laps after star award

    updated_kid_info = query_db("SELECT k.balloons, k.train_track_length, k.train_laps_completed, COUNT(s.id) as stars_count FROM kids k LEFT JOIN stars s ON k.id = s.kid_id WHERE k.id = ? GROUP BY k.id", (kid_id,), one=True)
    return jsonify({"message": "Chore marked complete!", "balloons_awarded": 1, "stars_from_balloons": stars_from_balloons, "daily_star_awarded": daily_star_awarded_this_action, "updated_kid_stats": dict(updated_kid_info) if updated_kid_info else {}}), 200

@app.route('/api/completions/uncheck', methods=['POST']) # Uncheck chore
def uncheck_chore_complete():
    data = request.json; kid_id = data.get('kidId'); assignment_id = data.get('assignmentId')
    today_date_obj = date.today(); today_date_str = today_date_obj.isoformat()
    if not kid_id or not assignment_id: return jsonify({"error": "Kid ID and Assignment ID are required"}), 400

    completion_to_delete = query_db("SELECT id FROM chore_completions WHERE assignment_id = ? AND kid_id = ? AND date_completed = ?", (assignment_id, kid_id, today_date_str), one=True)
    if not completion_to_delete: return jsonify({"message": "Chore was not marked as complete for today or already unchecked."}), 200
    
    execute_db("DELETE FROM chore_completions WHERE id = ?", (completion_to_delete['id'],))
    
    # Decrement balloon
    kid_balloons_before = query_db("SELECT balloons FROM kids WHERE id = ?", (kid_id,), one=True)['balloons']
    if kid_balloons_before > 0:
        execute_db("UPDATE kids SET balloons = balloons - 1 WHERE id = ?", (kid_id,))
    
    # Check if a daily star needs to be revoked
    daily_star_revoked = False
    chores_due_today = get_chores_for_kid_today_internal(kid_id, today_date_obj) # Re-check completion status
    all_done_after_uncheck = all(c['completed_today'] for c in chores_due_today) if chores_due_today else False
    
    daily_star_record = query_db("SELECT id FROM stars WHERE kid_id = ? AND date_awarded = ? AND type = 'daily'", (kid_id, today_date_str), one=True)
    if daily_star_record and not all_done_after_uncheck:
        execute_db("DELETE FROM stars WHERE id = ?", (daily_star_record['id'],))
        daily_star_revoked = True
        update_train_laps(kid_id) # Recalculate laps

    # Check if a balloon_conversion star needs to be revoked
    # This is complex: if unchecking causes balloons to drop below a multiple of BALLOONS_PER_STAR,
    # and a conversion star was awarded *today* due to that threshold.
    star_from_balloons_revoked = False
    if kid_balloons_before % BALLOONS_PER_STAR == 0 and kid_balloons_before > 0: # This chore's balloon might have caused a star
        # If after decrementing 1 balloon, we are now at (multiple of BALLOONS_PER_STAR) - 1
        current_balloons = query_db("SELECT balloons FROM kids WHERE id = ?", (kid_id,), one=True)['balloons']
        if current_balloons == (BALLOONS_PER_STAR - 1): # e.g., went from 10 to 9, or 20 to 19
            # Check if a balloon_conversion star was awarded today
            conversion_star = query_db("SELECT id FROM stars WHERE kid_id = ? AND date_awarded = ? AND type = 'balloon_conversion' ORDER BY id DESC LIMIT 1", (kid_id, today_date_str), one=True)
            if conversion_star:
                execute_db("DELETE FROM stars WHERE id = ?", (conversion_star['id'],))
                execute_db("UPDATE kids SET balloons = balloons + ? WHERE id = ?", (BALLOONS_PER_STAR -1, kid_id,)) # Give back (BALLOONS_PER_STAR - 1) balloons (total 9 if 10/star)
                star_from_balloons_revoked = True
                update_train_laps(kid_id) # Recalculate laps

    updated_kid_info = query_db("SELECT k.balloons, k.train_track_length, k.train_laps_completed, COUNT(s.id) as stars_count FROM kids k LEFT JOIN stars s ON k.id = s.kid_id WHERE k.id = ? GROUP BY k.id", (kid_id,), one=True)
    return jsonify({"message": "Chore unchecked.", "daily_star_revoked": daily_star_revoked, "star_from_balloons_revoked": star_from_balloons_revoked, "updated_kid_stats": dict(updated_kid_info) if updated_kid_info else {}}), 200

# --- Bonus Stars API (Updated for laps) ---
@app.route('/api/stars/bonus', methods=['POST'])
def award_bonus_star():
    if not check_admin_auth(): return jsonify({"error": "Unauthorized"}), 401
    data = request.json; kid_id = data.get('kidId'); reason = data.get('reason', '')
    today_date_str = date.today().isoformat()
    if not kid_id: return jsonify({"error": "Kid ID is required"}), 400
    execute_db("INSERT INTO stars (kid_id, date_awarded, type, reason) VALUES (?, ?, 'bonus', ?)", (kid_id, today_date_str, reason))
    update_train_laps(kid_id) # Update laps after star award
    return jsonify({"message": "Bonus star awarded"}), 201

# --- Admin Reset & Decrement Endpoints ---
@app.route('/api/admin/kids/<int:kid_id>/reset-daily-chores', methods=['POST'])
def admin_reset_daily_chores():
    if not check_admin_auth(): return jsonify({"error": "Unauthorized"}), 401
    today_date_str = date.today().isoformat()
    # Delete today's completions for the kid
    execute_db("DELETE FROM chore_completions WHERE kid_id = ? AND date_completed = ?", (kid_id, today_date_str))
    # Delete any daily star awarded today for this kid
    daily_star_record = query_db("SELECT id FROM stars WHERE kid_id = ? AND date_awarded = ? AND type = 'daily'", (kid_id, today_date_str), one=True)
    if daily_star_record:
        execute_db("DELETE FROM stars WHERE id = ?", (daily_star_record['id'],))
        update_train_laps(kid_id) # Recalculate laps
    return jsonify({"message": f"Daily chores and daily star (if any) for kid {kid_id} reset for today."}), 200

@app.route('/api/admin/kids/<int:kid_id>/decrement-balloons', methods=['POST'])
def admin_decrement_balloons():
    if not check_admin_auth(): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    count = data.get('count', 1)
    try: count = int(count)
    except ValueError: return jsonify({"error": "Invalid count"}), 400
    if count <= 0: return jsonify({"error": "Count must be positive"}), 400

    current_balloons = query_db("SELECT balloons FROM kids WHERE id = ?", (kid_id,), one=True)['balloons']
    new_balloons = max(0, current_balloons - count)
    execute_db("UPDATE kids SET balloons = ? WHERE id = ?", (new_balloons, kid_id))
    return jsonify({"message": f"{count} balloon(s) decremented for kid {kid_id}. New total: {new_balloons}."}), 200

@app.route('/api/admin/kids/<int:kid_id>/decrement-stars', methods=['POST'])
def admin_decrement_stars():
    if not check_admin_auth(): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    count = data.get('count', 1)
    star_type_filter = data.get('type', None) # e.g., 'daily', 'bonus', 'balloon_conversion', or None for any
    try: count = int(count)
    except ValueError: return jsonify({"error": "Invalid count"}), 400
    if count <= 0: return jsonify({"error": "Count must be positive"}), 400

    # Fetch stars to delete (oldest first, or specific type)
    sql = "SELECT id FROM stars WHERE kid_id = ?"
    params = [kid_id]
    if star_type_filter and star_type_filter != "any":
        sql += " AND type = ?"
        params.append(star_type_filter)
    sql += " ORDER BY date_awarded ASC, id ASC LIMIT ?" # Delete oldest stars first
    params.append(count)
    
    stars_to_delete = query_db(sql, tuple(params))
    
    if not stars_to_delete:
        return jsonify({"message": "No matching stars found to decrement."}), 404

    for star_row in stars_to_delete:
        execute_db("DELETE FROM stars WHERE id = ?", (star_row['id'],))
    
    update_train_laps(kid_id) # Recalculate laps
    return jsonify({"message": f"{len(stars_to_delete)} star(s) decremented for kid {kid_id}."}), 200

@app.route('/api/admin/kids/<int:kid_id>/train-config', methods=['PUT'])
def admin_configure_train_track():
    if not check_admin_auth(): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    track_length = data.get('train_track_length')
    try: track_length = int(track_length)
    except (ValueError, TypeError): return jsonify({"error": "Invalid track length"}), 400
    if track_length <= 0: return jsonify({"error": "Track length must be positive"}), 400

    execute_db("UPDATE kids SET train_track_length = ? WHERE id = ?", (track_length, kid_id))
    update_train_laps(kid_id) # Recalculate laps with new track length
    return jsonify({"message": f"Train track length for kid {kid_id} updated to {track_length}."}), 200

# --- CLI command to initialize DB ---
@app.cli.command('initdb')
def initdb_command():
    db = get_db()
    db.cursor().executescript(SCHEMA_SQL)
    db.commit()
    print('Initialized the database with schema string.')

if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        print(f"Database {DATABASE} not found. Initializing...")
        with app.app_context():
            db = get_db()
            db.cursor().executescript(SCHEMA_SQL)
            db.commit()
            print("Database initialized.")
    app.run(host='0.0.0.0', port=5000, debug=True)
