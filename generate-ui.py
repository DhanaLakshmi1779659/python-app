from flask import Flask, render_template, jsonify, request, redirect, url_for, session
import json
import requests
import base64
import pdb

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for session management

# GitHub repository details
GITHUB_API_URL = 'https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}'
GITHUB_BRANCHES_URL = 'https://api.github.com/repos/{owner}/{repo}/branches'
GITHUB_PR_URL = 'https://api.github.com/repos/{owner}/{repo}/pulls'
GITHUB_OWNER = ''
GITHUB_REPO = ''
JSON_FILE_PATH = 'windows2019_policies.json'

# GitHub API token
GITHUB_TOKEN = ''

# Load JSON data from GitHub
def load_json(branch):
    url = GITHUB_API_URL.format(owner=GITHUB_OWNER, repo=GITHUB_REPO, path=JSON_FILE_PATH, branch=branch)
    response = requests.get(url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
    if response.status_code == 200:
        content = response.json().get('content')
        if content:
            decoded_content = base64.b64decode(content).decode('utf-8')
            return json.loads(decoded_content)
    return []

# Fetch the list of branches from GitHub
def fetch_branches():
    url = GITHUB_BRANCHES_URL.format(owner=GITHUB_OWNER, repo=GITHUB_REPO)
    response = requests.get(url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
    if response.status_code == 200:
        branches = response.json()
        return [branch['name'] for branch in branches]
    return []

# Save JSON data to GitHub with only the changes
def save_json(branch, original_data, updated_data):
    url = GITHUB_API_URL.format(owner=GITHUB_OWNER, repo=GITHUB_REPO, path=JSON_FILE_PATH, branch=branch)
    get_response = requests.get(url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
    if get_response.status_code == 200:
        sha = get_response.json().get('sha')
        # Identify changes
        changes = []
        for index, (orig, updated) in enumerate(zip(original_data, updated_data)):
            if orig != updated:
                changes.append((index, updated))
        # Apply changes to original data
        for index, updated in changes:
            original_data[index] = updated
        encoded_content = base64.b64encode(json.dumps(original_data).encode('utf-8')).decode('utf-8')
        commit_message = f"Update {JSON_FILE_PATH} on branch {branch} with changes"
        update_data = {
            "message": commit_message,
            "content": encoded_content,
            "sha": sha,
            "branch": branch
        }
        update_response = requests.put(url, headers={'Authorization': f'token {GITHUB_TOKEN}'}, json=update_data)
        return update_response.status_code == 200
    return False

# Promote changes by creating a pull request
def promote_changes(branch, target_branch):
    url = GITHUB_PR_URL.format(owner=GITHUB_OWNER, repo=GITHUB_REPO)
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    data = {
        "title": "Promote changes",
        "head": branch,
        "base": target_branch,
        "body": "Promoting changes from branch to target branch"
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('form'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Simple authentication
        if username == 'admin' and password == 'password':
            session['username'] = username
            return redirect(url_for('form'))
        else:
            return render_template('login.html', error='Invalid Credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/form')
def form():
    if 'username' not in session:
        return redirect(url_for('login'))
    branches = fetch_branches()
    return render_template('form.html', branches=branches)

@app.route('/get-json')
def get_json():
    branch = request.args.get('branch', 'main')  # Default to 'main' branch
    data = load_json(branch)
    return jsonify(data)

@app.route('/submit', methods=['POST'])
def submit():
    branch = request.json.get('branch', 'main')  # Default to 'main' branch
    updated_data = request.json.get('data')
    print("updated data")
    print(updated_data)
    original_data = load_json(branch)
    success = save_json(branch, original_data, updated_data)
    if success:
        return jsonify({"message": "Data updated successfully!"})
    else:
        return jsonify({"message": "Failed to update data!"}), 500

@app.route('/remove', methods=['POST'])
def remove():
    row_id = request.json.get('id')
    branch = request.json.get('branch', 'main')  # Default to 'main' branch
    data = load_json(branch)
    if 0 <= row_id < len(data):
        data.pop(row_id)
        success = save_json(branch, data, data)
        if success:
            return jsonify({"message": "Row removed successfully!"})
        else:
            return jsonify({"message": "Failed to update data!"}), 500
    return jsonify({"message": "Invalid row ID!"}), 400

@app.route('/promote', methods=['POST'])
def promote():
    branch = request.json.get('branch')
    target_branch = request.json.get('target_branch')
    result = promote_changes(branch, target_branch)
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)
===================================
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dynamic JSON Form</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            font-family: 'Arial', sans-serif;
            font-size: 12px;
            background-color: #f8f9fa;
        }
        .navbar {
            background-color: navy;
        }
        .navbar-brand,
        .navbar-nav .nav-link {
            color: white !important;
            font-weight: bold;
        }
        .navbar-brand img {
            max-height: 40px;
        }
        .table {
            table-layout: auto;
            width: 100%;
            word-wrap: break-word;
        }
        .table th, .table td {
            text-align: left;
            vertical-align: top;
            padding: 8px;
            border: 1px solid #dee2e6;
            white-space: normal;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }
        .table th {
            white-space: nowrap;
            font-size: 15px;
            font-weight: bold;
            background-color: #d5e8ff;
            color: #000;
            border: 1px solid #dee2e6;
            text-align: center;
        }
        .pagination-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: nowrap;
            gap: 15px;
        }
        textarea {
            resize: none;
            overflow-wrap: break-word;
            font-size: 14px;
        }
        input, select {
            font-size: 14px;
        }
        .action-controls {
            display: flex;
            justify-content: flex-end;
            gap: 15px;
            align-items: center;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">
                <img src="https://via.placeholder.com/150x40" alt="Company Logo">
            </a>
            <ul class="navbar-nav ms-auto">
                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle" href="#" id="userDropdown" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                        <i class="bi bi-person-circle"></i> User
                    </a>
                    <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="userDropdown">
                        <li><a class="dropdown-item" href="#">Profile</a></li>
                        <li><a class="dropdown-item" href="/logout">Logout</a></li>
                    </ul>
                </li>
            </ul>
        </div>
    </nav>

    <div class="container mt-5">
        <div class="card">
            <div class="card-body">
                <h2 class="card-title mb-4">Windows 2019 Security Policies Updater</h2>
                <form id="dynamicForm">
                    <div class="mb-3">
                        <label for="branchSelect" class="form-label">Select GitHub Branch:</label>
                        <select id="branchSelect" class="form-select" onchange="fetchData()">
                            {% for branch in branches %}
                            <option value="{{ branch }}">{{ branch }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <table class="table">
                        <thead id="tableHeaders"></thead>
                        <tbody id="tableBody"></tbody>
                    </table>
                    <div class="pagination-container mt-3">
                        <ul class="pagination"></ul>
                        <div class="action-controls">
                            <button type="button" class="btn btn-success" onclick="addRow()">+ Add Row</button>
                            <button type="button" class="btn btn-primary ms-3" id="showAllRowsButton">Show All</button>
                            <span>Go to page:</span>
                            <input type="number" id="gotoPage" class="form-control d-inline" style="width: 60px;" min="1">
                            <button class="btn btn-secondary ms-2" type="button" id="gotoButton">Go</button>
                        </div>
                    </div>
                    <div class="d-flex justify-content-end gap-2 mt-3">
                        <button type="button" class="btn btn-secondary" onclick="cancelChanges()">Cancel</button>
                        <button type="button" class="btn btn-primary" onclick="submitForm()">Submit</button>
                    </div>
                    <div class="mt-3">
                        <label for="targetBranchSelect" class="form-label">Select Target Branch for Promotion:</label>
                        <select id="targetBranchSelect" class="form-select">
                            {% for branch in branches %}
                            <option value="{{ branch }}">{{ branch }}</option>
                            {% endfor %}
                        </select>
                        <button type="button" class="btn btn-warning mt-2" onclick="promoteChanges()">Promote Changes</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.1/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let rowsPerPage = 5;
        let currentPage = 1;
        let jsonData = [];
        let originalData = [];

        function sanitizeData(data) {
            return data.map(row => {
                const sanitizedRow = {};
                Object.keys(row).forEach(key => {
                    sanitizedRow[key] = typeof row[key] === 'string'
                        ? row[key].replace(/\s+/g, ' ').trim()
                        : row[key];
                });
                return sanitizedRow;
            });
        }

        async function fetchData() {
            const branch = document.getElementById('branchSelect').value;
            const response = await fetch(`/get-json?branch=${branch}`);
            jsonData = sanitizeData(await response.json());
            originalData = JSON.parse(JSON.stringify(jsonData)); // Deep copy of original data
            renderTable();
            paginate();
        }

        function renderTable() {
            if (!jsonData || jsonData.length === 0) {
                console.error("No data to render.");
                return;
            }

            const headers = Object.keys(jsonData[0]);
            const tableHeaders = document.getElementById('tableHeaders');
            const tableBody = document.getElementById('tableBody');
            tableHeaders.innerHTML = '';
            tableBody.innerHTML = '';

            const headerRow = document.createElement('tr');
            headers.forEach(header => {
                const th = document.createElement('th');
                th.textContent = header;
                th.style.backgroundColor = '#d5e8ff';
                th.style.fontSize = '15px';
                th.style.fontWeight = 'bold';
                headerRow.appendChild(th);
            });
            headerRow.appendChild(document.createElement('th'));
            tableHeaders.appendChild(headerRow);

            jsonData.forEach((row, index) => {
                const tableRow = document.createElement('tr');
                headers.forEach(header => {
                    const td = document.createElement('td');
                    if (header === 'Enabled') {
                        const select = document.createElement('select');
                        select.className = 'form-select';
                        ['True', 'False'].forEach(value => {
                            const option = document.createElement('option');
                            option.value = value;
                            option.textContent = value;
                            if (row[header] === value) option.selected = true;
                            select.appendChild(option);
                        });
                        td.appendChild(select);
                    } else {
                        const textarea = document.createElement('textarea');
                        textarea.className = 'form-control';
                        textarea.value = row[header] !== undefined ? row[header] : '';
                        td.appendChild(textarea);
                    }
                    tableRow.appendChild(td);
                });

                const removeButtonTd = document.createElement('td');
                const removeButton = document.createElement('button');
                removeButton.className = 'btn btn-danger';
                removeButton.textContent = 'Remove';
                removeButton.onclick = () => removeRow(index);
                removeButtonTd.appendChild(removeButton);
                tableRow.appendChild(removeButtonTd);
                tableBody.appendChild(tableRow);
            });
        }

        function paginate() {
            const rows = document.querySelectorAll("#tableBody tr");
            const pagination = document.querySelector(".pagination");
            const totalRows = rows.length;

            rows.forEach((row, index) => {
                row.style.display =
                    index >= (currentPage - 1) * rowsPerPage && index < currentPage * rowsPerPage
                        ? ''
                        : 'none';
            });

            const totalPages = Math.ceil(totalRows / rowsPerPage);
            const maxVisiblePages = 5;
            let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
            let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);

            if (endPage - startPage + 1 < maxVisiblePages) {
                startPage = Math.max(1, endPage - maxVisiblePages + 1);
            }

            pagination.innerHTML = `
                <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                    <a class="page-link" href="#" onclick="setPage(1)">First</a>
                </li>
                <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                    <a class="page-link" href="#" onclick="setPage(currentPage - 1)">Prev</a>
                </li>
            `;

            for (let i = startPage; i <= endPage; i++) {
                pagination.innerHTML += `
                    <li class="page-item ${i === currentPage ? 'active' : ''}">
                        <a class="page-link" href="#" onclick="setPage(${i})">${i}</a>
                    </li>
                `;
            }

            pagination.innerHTML += `
                <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                    <a class="page-link" href="#" onclick="setPage(currentPage + 1)">Next</a>
                </li>
                <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                    <a class="page-link" href="#" onclick="setPage(${totalPages})">Last</a>
                </li>
            `;
        }

        function setPage(page) {
            const rows = document.querySelectorAll("#tableBody tr");
            const totalPages = Math.ceil(rows.length / rowsPerPage);
            currentPage = Math.max(1, Math.min(page, totalPages));
            paginate();
        }

        function gotoPage() {
            const pageInput = document.getElementById('gotoPage');
            const page = parseInt(pageInput.value, 10);
            const totalPages = Math.ceil(jsonData.length / rowsPerPage);

            if (!isNaN(page) && page > 0 && page <= totalPages) {
                setPage(page);
            } else {
                alert(`Invalid page number. Please enter a number between 1 and ${totalPages}.`);
            }
        }

        function showAllRows() {
            rowsPerPage = jsonData.length;
            currentPage = 1;
            paginate();
        }

        function addRow() {
            const headers = Object.keys(jsonData[0] || {});
            const newRow = headers.reduce((acc, header) => {
                acc[header] = header === 'Enabled' ? 'True' : '';
                return acc;
            }, {});

            jsonData.push(newRow);
            renderTable();
            currentPage = Math.ceil(jsonData.length / rowsPerPage);
            paginate();
        }

        function cancelChanges() {
            if (confirm('Are you sure you want to cancel changes?')) {
                window.location.reload();
            }
        }

        async function removeRow(index) {
            const branch = document.getElementById('branchSelect').value;
            const response = await fetch('/remove', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: index, branch: branch }),
            });

            const result = await response.json();
            alert(result.message || 'Error');
            if (result.message === "Row removed successfully!") {
                fetchData();
            }
        }

        async function submitForm() {
            const rows = document.querySelectorAll('#tableBody tr');
            const headers = Object.keys(jsonData[0] || {});
            const branch = document.getElementById('branchSelect').value;

            const updatedData = Array.from(rows).map(row => {
                const cells = row.querySelectorAll('td');
                return headers.reduce((acc, header, index) => {
                    const cell = cells[index];
                    acc[header] = header === 'Enabled'
                        ? cell.querySelector('select').value
                        : cell.querySelector('textarea').value;
                    return acc;
                }, {});
            });

            const response = await fetch('/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ data: updatedData, branch: branch }),
            });

            const result = await response.json();
            alert(result.message || 'Error');
        }

        async function promoteChanges() {
            const branch = document.getElementById('branchSelect').value;
            const targetBranch = document.getElementById('targetBranchSelect').value;

            const response = await fetch('/promote', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ branch: branch, target_branch: targetBranch }),
            });

            const result = await response.json();
            alert(result.message || 'Promotion request sent.');
        }

        document.addEventListener('DOMContentLoaded', () => {
            document.getElementById('gotoButton').addEventListener('click', gotoPage);
            document.getElementById('showAllRowsButton').addEventListener('click', showAllRows);
            fetchData();
        });
    </script>
</body>
</html>
=============================
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            background-color: #f8f9fa;
        }
        .login-container {
            width: 300px;
            padding: 20px;
            border: 1px solid #dee2e6;
            border-radius: 10px;
            background-color: white;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h2 class="text-center mb-4">Login</h2>
        {% if error %}
        <div class="alert alert-danger">{{ error }}</div>
        {% endif %}
        <form method="POST">
            <div class="mb-3">
                <label for="username" class="form-label">Username</label>
                <input type="text" class="form-control" id="username" name="username" required>
            </div>
            <div class="mb-3">
                <label for="password" class="form-label">Password</label>
                <input type="password" class="form-control" id="password" name="password" required>
            </div>
            <button type="submit" class="btn btn-primary w-100">Login</button>
        </form>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.1/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
