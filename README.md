# DB Tester Toolkit

A lightweight desktop-style tool that helps **functional testers** inspect and validate databases without writing complex SQL. Connect to **Oracle, SQL Server, MySQL/MariaDB or SQLite**, build joins visually, compare data and run quick data-quality checks.

It runs locally as a small web app (Flask) that opens in your browser, and can be packaged into a single Windows `.exe`.

## Features

| Feature | What it does |
|---|---|
| **Connection manager** | Save profiles with host, port, credentials or a full connection string. Test and connect with one click. |
| **Schema browser** | Tables, columns, types, row counts, primary keys and foreign keys. |
| **Visual join builder** | Pick tables, join types and columns. Joins are auto-suggested from foreign keys and the SQL is generated for you. |
| **SQL editor** | Run queries, view results, export to CSV, reuse query history. |
| **Compare** | Diff two result sets (before vs after, source vs target), even across different databases such as Oracle vs SQL Server. Shows rows only in A, only in B and changed values. |
| **Data checks** | Automatic row-count, NULL, duplicate and orphan-foreign-key checks, per table or for all tables. |
| **Snapshots** | Save row counts before a test and compare after it to see which tables changed. |
| **Read-only mode** | On by default. Only `SELECT` / `WITH` queries are allowed until you turn it off. |

## Supported databases

| Database | Driver | Notes |
|---|---|---|
| Oracle | `oracledb` (thin mode) | No Oracle client needed. Service name or SID, optional schema/owner. |
| SQL Server | `pyodbc` | Needs *ODBC Driver 17 or 18 for SQL Server* installed. SQL login or Windows authentication. |
| MySQL / MariaDB | `PyMySQL` | Pure Python, no client needed. |
| SQLite | built-in | Includes a Demo profile with sample data. |

## Quick start (build the .exe on Windows)

1. Install **Python 3.9+** and tick **Add Python to PATH**.
2. Download or clone this repository.
3. Double-click `build_exe.bat`.
4. Run `dist\DBTesterToolkit.exe`. Your browser opens the app.

Try the built-in **Demo (SQLite)** profile first to see how everything works.

### Run without building the exe

```bash
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5055 if the browser does not open automatically. Use the `PORT` environment variable to change the port.

## How to use

1. **Connections**: add a profile (name, type, host, port, database/service, user, password) and click **Test**, then **Connect**.
2. **Schema**: review tables and relationships.
3. **Join Builder**: choose a start table, click **Add join**, tick the columns you need, then **Run join**. Use **Open in SQL editor** to fine-tune the SQL.
4. **Compare**: choose a connection and a query for each side, optionally enter key column(s), and click **Compare**.
5. **Data Checks / Snapshots**: validate data quality and track changes made by a test.

## Safety and security

- **Read-only by default.** Untick *Read-only mode* in the top bar only when you intentionally need `INSERT`, `UPDATE` or `DELETE`. Never point write-enabled sessions at production.
- Profiles are stored on your PC in `~/.dbtester` (`connections.json`, `snapshots.json`, `history.json`).
- **Passwords are only lightly obfuscated (base64), not strongly encrypted.** Do not use this on shared machines with sensitive production credentials. Use dedicated read-only test accounts.
- The server listens on `127.0.0.1` only, so it is not reachable from other machines.
- Do not commit `~/.dbtester` files or real credentials to Git.

## Project structure

```
app.py               Flask backend: connections, schema, queries, compare, checks, snapshots
templates/index.html Single-page UI
requirements.txt     Python dependencies
build_exe.bat        Builds dist\DBTesterToolkit.exe with PyInstaller
```

## Troubleshooting

| Problem | Fix |
|---|---|
| SQL Server: "No SQL Server ODBC driver found" | Install *ODBC Driver 17 or 18 for SQL Server*. |
| Oracle: login or connect error | Check host, port and service name vs SID. Try the full connection string field (`host:1521/service`). |
| MySQL: connection refused | Confirm port 3306 and that the user is allowed to connect from your PC. |
| "Read-only mode is ON" error | Untick *Read-only mode* if you really need to run a change. |
| Build fails | Check Python is on PATH and re-run `build_exe.bat`. |

## Limitations

- Result display is capped (default 500 rows) to keep the UI fast.
- Row-count snapshots track counts only, not full table contents.
- One statement per query.

## License

Add your preferred license here (for example MIT).
