DB Tester Toolkit (Oracle + SQL Server + SQLite)
1. Install Python 3.9+ (tick "Add to PATH").
2. Double-click build_exe.bat  ->  dist\DBTesterToolkit.exe
3. Run the exe. Your browser opens the app. A Demo (SQLite) profile is included.

ORACLE: no Oracle client needed (python-oracledb thin mode). Choose Service name or SID. Optional Schema/owner.
SQL SERVER: needs "ODBC Driver 17 or 18 for SQL Server" on the PC. Supports SQL login or Windows authentication.
Read-only mode is ON by default; untick it in the top bar to allow INSERT/UPDATE/DELETE.
