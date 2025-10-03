import pytest
import json
from unittest.mock import Mock, patch, call
import requests
from meal_planner_app import generate_shopping_list, get_random_meal, generate_meals_with_gemini

# --- Test Data ---

MOCK_MEAL_PLAN_1 = {
    "Monday": {
        "Lunch": {
            "name": "Chicken Salad",
            "ingredients": [
                {"item": "Chicken Breast", "quantity": 1, "unit": "piece"},
                {"item": "Mayonnaise", "quantity": 2, "unit": "tbsp"},
                {"item": "Celery", "quantity": 1, "unit": "stalk"},
            ],
        },
        "Dinner": {
            "name": "Spaghetti Bolognese",
            "ingredients": [
                {"item": "Ground Beef", "quantity": 500, "unit": "g"},
                {"item": "Spaghetti", "quantity": 200, "unit": "g"},
                {"item": "Tomato Sauce", "quantity": 1, "unit": "can"},
            ],
        },
    }
}

MOCK_MEAL_PLAN_2 = {
    "Tuesday": {
        "Lunch": {
            "name": "Tuna Sandwich",
            "ingredients": [
                {"item": "Tuna", "quantity": 1, "unit": "can"},
                {"item": "Bread", "quantity": 2, "unit": "slice"},
                {"item": "Mayonnaise", "quantity": 1, "unit": "tbsp"},
            ],
        },
    },
    "Wednesday": {
        "Dinner": {
            "name": "More Tuna",
            "ingredients": [
                {"item": "Tuna", "quantity": 2, "unit": "can"},
                {"item": "Olive Oil", "quantity": 1, "unit": "tbsp"},
            ],
        },
    }
}


# --- Tests for generate_shopping_list ---

def test_generate_shopping_list_basic():
    """Tests basic shopping list generation from a simple meal plan."""
    pantry = ["Salt", "Pepper"]
    expected_list = (
        "- Celery: 1 stalk\n"
        "- Chicken Breast: 1 piece\n"
        "- Ground Beef: 500 g\n"
        "- Mayonnaise: 2 tbsps\n"
        "- Spaghetti: 200 g\n"
        "- Tomato Sauce: 1 can\n"
    )
    assert generate_shopping_list(MOCK_MEAL_PLAN_1, pantry) == expected_list

def test_generate_shopping_list_with_pantry_items():
    """Tests that items already in the pantry are excluded from the list."""
    pantry = ["Mayonnaise", "Spaghetti", "Tomato Sauce", "chicken breast"] # Test case-insensitivity
    expected_list = (
        "- Celery: 1 stalk\n"
        "- Ground Beef: 500 g\n"
    )
    assert generate_shopping_list(MOCK_MEAL_PLAN_1, pantry) == expected_list

def test_generate_shopping_list_aggregates_quantities():
    """Tests that quantities of the same item are correctly aggregated."""
    pantry = ["Olive Oil"]
    expected_list = (
        "- Bread: 2 slices\n"
        "- Mayonnaise: 1 tbsp\n"
        "- Tuna: 3 cans\n"
    )
    assert generate_shopping_list(MOCK_MEAL_PLAN_2, pantry) == expected_list

def test_generate_shopping_list_empty_meal_plan():
    """Tests behavior with an empty meal plan."""
    pantry = ["Salt"]
    assert generate_shopping_list({}, pantry) == "You have everything you need!"

def test_generate_shopping_list_all_items_in_pantry():
    """Tests the case where all required ingredients are in the pantry."""
    pantry = [
        "Chicken Breast", "Mayonnaise", "Celery",
        "Ground Beef", "Spaghetti", "Tomato Sauce"
    ]
    assert generate_shopping_list(MOCK_MEAL_PLAN_1, pantry) == "You have everything you need!"

def test_generate_shopping_list_handles_empty_meal_or_ingredients():
    """Tests robustness against meals without an 'ingredients' key or empty meals."""
    meal_plan = {
        "Monday": {
            "Lunch": {"name": "Leftovers"},
            "Dinner": None,
        },
        "Tuesday": {
            "Lunch": {
                "name": "Salad",
                "ingredients": [
                    {"item": "Lettuce", "quantity": 1, "unit": "head"}
                ]
            }
        }
    }
    pantry = []
    expected_list = "- Lettuce: 1 head\n"
    assert generate_shopping_list(meal_plan, pantry) == expected_list


# --- Helper for mocking streamlit.session_state ---

class MockSessionState(dict):
    """A mock object that mimics streamlit.session_state."""
    def __init__(self, *args, **kwargs):
        super(MockSessionState, self).__init__(*args, **kwargs)
        self.__dict__ = self

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)

    def __setattr__(self, key, value):
        self[key] = value


# --- Test Data for get_random_meal ---
MOCK_GENERATED_MEALS = {
    "Lunch": [
        {"name": "Tuna Sandwich", "ingredients": [], "instructions": ""},
        {"name": "Chicken Wrap", "ingredients": [], "instructions": ""},
    ],
    "QuickDinner": [
        {"name": "Pasta Aglio e Olio", "ingredients": [], "instructions": ""},
    ]
}


# --- Tests for get_random_meal ---

@patch('meal_planner_app.st')
def test_get_random_meal_selects_a_meal(mock_st):
    """Tests that a random meal is returned from the specified list."""
    mock_st.session_state = MockSessionState(generated_meals=MOCK_GENERATED_MEALS)
    meal = get_random_meal('Lunch')
    assert meal['name'] in ["Tuna Sandwich", "Chicken Wrap"]

@patch('meal_planner_app.st')
def test_get_random_meal_avoids_existing_meal(mock_st):
    """Tests that a different meal is chosen if an existing meal is provided."""
    mock_st.session_state = MockSessionState(generated_meals=MOCK_GENERATED_MEALS)
    existing_meal = {"name": "Tuna Sandwich", "ingredients": [], "instructions": ""}
    meal = get_random_meal('Lunch', existing_meal=existing_meal)
    assert meal['name'] == "Chicken Wrap"

@patch('meal_planner_app.st')
def test_get_random_meal_only_one_option(mock_st):
    """Tests that the only meal is returned if it's also the existing meal."""
    mock_st.session_state = MockSessionState(generated_meals=MOCK_GENERATED_MEALS)
    existing_meal = {"name": "Pasta Aglio e Olio", "ingredients": [], "instructions": ""}
    meal = get_random_meal('QuickDinner', existing_meal=existing_meal)
    assert meal['name'] == "Pasta Aglio e Olio"

@patch('meal_planner_app.st')
def test_get_random_meal_no_meals_for_type(mock_st):
    """Tests the function's behavior when a meal type has an empty list."""
    mock_st.session_state = MockSessionState(generated_meals={"Lunch": []})
    result = get_random_meal('Lunch')
    assert result['name'] == "No meals found for this style."

@patch('meal_planner_app.st')
def test_get_random_meal_no_generated_meals_key_missing(mock_st):
    """Tests graceful failure when 'generated_meals' key is missing from session_state."""
    mock_st.session_state = MockSessionState()
    result = get_random_meal('Lunch')
    assert result['name'] == "Generate a meal plan first!"

@patch('meal_planner_app.st')
def test_get_random_meal_no_generated_meals_is_none(mock_st):
    """Tests graceful failure when 'generated_meals' is None in session_state."""
    mock_st.session_state = MockSessionState(generated_meals=None)
    result = get_random_meal('Lunch')
    assert result['name'] == "Generate a meal plan first!"


# --- Test Data for generate_meals_with_gemini ---

MOCK_API_RESPONSE = {
    "candidates": [{
        "content": {
            "parts": [{
                "text": json.dumps({"Lunch": [{"name": "Test Lunch"}]})
            }]
        }
    }]
}

# --- Tests for generate_meals_with_gemini ---

@patch('meal_planner_app.requests.post')
@patch('meal_planner_app.st')
def test_generate_meals_quick_cook_only(mock_st, mock_post):
    """Verify payload for 'Quick Cook' dinners only."""
    mock_st.secrets = {"GEMINI_API_KEY": "TEST_KEY"}
    mock_post.return_value.ok = True
    mock_post.return_value.json.return_value = MOCK_API_RESPONSE

    dinner_settings = {
        "Monday": {'plan': True, 'style': "Quick Cook (<30 mins)"},
        "Tuesday": {'plan': False, 'style': "Full Cook (longer prep)"}
    }

    generate_meals_with_gemini("any", dinner_settings)

    args, kwargs = mock_post.call_args
    payload = kwargs['json']

    # Check that only QuickDinner is in the schema
    assert "QuickDinner" in payload['generationConfig']['responseSchema']['properties']
    assert "FullDinner" not in payload['generationConfig']['responseSchema']['properties']
    # Check that the prompt is correct
    assert "quick-cook" in payload['contents'][0]['parts'][0]['text']
    assert "full cook" not in payload['contents'][0]['parts'][0]['text']


@patch('meal_planner_app.requests.post')
@patch('meal_planner_app.st')
def test_generate_meals_full_cook_only(mock_st, mock_post):
    """Verify payload for 'Full Cook' dinners only."""
    mock_st.secrets = {"GEMINI_API_KEY": "TEST_KEY"}
    mock_post.return_value.ok = True
    mock_post.return_value.json.return_value = MOCK_API_RESPONSE

    dinner_settings = {
        "Monday": {'plan': False, 'style': "Quick Cook (<30 mins)"},
        "Tuesday": {'plan': True, 'style': "Full Cook (longer prep)"}
    }

    generate_meals_with_gemini("any", dinner_settings)

    args, kwargs = mock_post.call_args
    payload = kwargs['json']

    assert "FullDinner" in payload['generationConfig']['responseSchema']['properties']
    assert "QuickDinner" not in payload['generationConfig']['responseSchema']['properties']
    assert "full cook" in payload['contents'][0]['parts'][0]['text']
    assert "quick-cook" not in payload['contents'][0]['parts'][0]['text']

@patch('meal_planner_app.requests.post')
@patch('meal_planner_app.st')
def test_generate_meals_mixed_cook_styles(mock_st, mock_post):
    """Verify payload for both 'Quick Cook' and 'Full Cook' dinners."""
    mock_st.secrets = {"GEMINI_API_KEY": "TEST_KEY"}
    mock_post.return_value.ok = True
    mock_post.return_value.json.return_value = MOCK_API_RESPONSE

    dinner_settings = {
        "Monday": {'plan': True, 'style': "Quick Cook (<30 mins)"},
        "Tuesday": {'plan': True, 'style': "Full Cook (longer prep)"}
    }

    generate_meals_with_gemini("any", dinner_settings)

    args, kwargs = mock_post.call_args
    payload = kwargs['json']

    assert "QuickDinner" in payload['generationConfig']['responseSchema']['properties']
    assert "FullDinner" in payload['generationConfig']['responseSchema']['properties']
    assert "quick-cook" in payload['contents'][0]['parts'][0]['text']
    assert "full cook" in payload['contents'][0]['parts'][0]['text']

@patch('meal_planner_app.requests.post')
@patch('meal_planner_app.st')
def test_generate_meals_handles_successful_response(mock_st, mock_post):
    """Test successful API response parsing."""
    mock_st.secrets = {"GEMINI_API_KEY": "TEST_KEY"}
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.return_value = MOCK_API_RESPONSE

    result = generate_meals_with_gemini("any", {})

    assert result == {"Lunch": [{"name": "Test Lunch"}]}

@patch('meal_planner_app.requests.post')
@patch('meal_planner_app.st')
def test_generate_meals_handles_request_exception(mock_st, mock_post):
    """Test handling of a requests.RequestException."""
    mock_st.secrets = {"GEMINI_API_KEY": "TEST_KEY"}
    mock_post.side_effect = requests.exceptions.RequestException("API Error")

    result = generate_meals_with_gemini("any", {})

    assert result is None
    mock_st.error.assert_called_with("API request failed: API Error")

@patch('meal_planner_app.requests.post')
@patch('meal_planner_app.st')
def test_generate_meals_handles_json_decode_error(mock_st, mock_post):
    """Test handling of invalid JSON in the API response."""
    mock_st.secrets = {"GEMINI_API_KEY": "TEST_KEY"}
    mock_post.return_value.raise_for_status.return_value = None
    # Simulate invalid JSON response
    response_payload = {
        "candidates": [{"content": {"parts": [{"text": "this is not json"}]}}]
    }
    mock_post.return_value.json.return_value = response_payload

    result = generate_meals_with_gemini("any", {})

    assert result is None
    # The f-string in the app code uses the string representation of the error, not the repr.
    expected_error_message = "Failed to parse API response: Expecting value: line 1 column 1 (char 0)"
    mock_st.error.assert_called_with(expected_error_message)

@patch('meal_planner_app.st')
def test_generate_meals_no_api_key(mock_st):
    """Test graceful failure when GEMINI_API_KEY is not found in secrets."""
    mock_st.secrets = {} # No API key

    result = generate_meals_with_gemini("any", {})

    assert result is None
    mock_st.error.assert_called_with("GEMINI_API_KEY not found. Please add it to your .streamlit/secrets.toml file.")