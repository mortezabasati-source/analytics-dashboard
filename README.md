# Streamlit Analytics Dashboard

This project is an analytical and executive dashboard built with Streamlit to visualize sales data from a MySQL database.

## Setup and Installation

1.  **Create a Virtual Environment:**
    ```bash
    python -m venv venv
    # On Windows: venv\Scripts\activate
    # On macOS/Linux: source venv/bin/activate
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure `.env`:**
    Fill in your MySQL database credentials in the `.env` file.

4.  **Run the App:**
    ```bash
    streamlit run src/app.py
    ```

## Idle sessions and browser tests

The dashboard warns after **5 idle minutes** and ends the session after
**10 idle minutes in total**. The user can explicitly continue from the warning.
Expiry navigates to a standalone browser page and closes the Streamlit WebSocket.

See [the session timeout guide](docs/session-timeout.md) for configuration,
Playwright test commands (including the actual ten-minute test), and Cloud Run
deployment considerations.
