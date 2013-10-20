"""
Core application code. This is the package that interfaces between the
presentation layer (Flask etc.), the database, external email, etc.

The dependency graph should look like:

Presentation -> Core
Admin -> Core
Background worker process -> Core
Core -> Database
Core -> Email

Note that these are all one-way dependencies, and that they all include Core.
"""
