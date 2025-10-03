# 🍽️ Gemini-Powered Meal Planner

A Streamlit web application that generates personalized weekly meal plans using the Google Gemini API.

## Features

-   **Dynamic Meal Generation:** Creates meal plans based on user-defined dietary preferences.
-   **Customizable Plan:** Select which days of the week you need meals for.
-   **Regenerate on the Fly:** Don't like a meal? Regenerate it with a single click.
-   **Smart Shopping List:** Generates a shopping list based on your plan, automatically excluding items you already have in your pantry.

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/meal-planner-app.git](https://github.com/your-username/meal-planner-app.git)
    cd meal-planner-app
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the required packages:**
    ```bash
    pip install -r requirements.txt
    ```

## How to Run

To start the Streamlit application, run the following command in your terminal:

```bash
streamlit run meal_planner_app.py
```

## To do

Integarte Nutrition API and Database