import streamlit as st
import random
import json
import requests

# --- HELPER FUNCTIONS ---

def generate_meals_with_gemini(dietary_prefs, selected_days):
    """
    Calls the Gemini API to generate a pool of meal ideas with instructions.
    Requests a structured JSON response.
    """
    # Securely access the API key from Streamlit's secrets
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        st.error("GEMINI_API_KEY not found in Streamlit secrets. Please add it to your .streamlit/secrets.toml file.")
        return None
        
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={api_key}"

    # Define the precise JSON structure, now including "instructions"
    json_schema = {
        "type": "OBJECT",
        "properties": {
            "Lunch": {
                "type": "ARRAY",
                "description": "A list of 7 diverse, prep-ahead lunch ideas suitable for one person.",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "name": {"type": "STRING", "description": "Creative and appealing name of the meal."},
                        "ingredients": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "item": {"type": "STRING"}, "quantity": {"type": "NUMBER"}, "unit": {"type": "STRING"}
                                }, "required": ["item", "quantity", "unit"]
                            }
                        },
                        "instructions": {"type": "STRING", "description": "Step-by-step cooking instructions as a single string with newlines."}
                    },
                    "required": ["name", "ingredients", "instructions"]
                }
            },
            "Dinner": {
                "type": "ARRAY",
                "description": "A list of 7 diverse, quick-cook dinner ideas suitable for two people.",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "name": {"type": "STRING"},
                        "ingredients": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "item": {"type": "STRING"}, "quantity": {"type": "NUMBER"}, "unit": {"type": "STRING"}
                                }, "required": ["item", "quantity", "unit"]
                            }
                        },
                        "instructions": {"type": "STRING", "description": "Step-by-step cooking instructions as a single string with newlines."}
                    },
                    "required": ["name", "ingredients", "instructions"]
                }
            }
        },
        "required": ["Lunch", "Dinner"]
    }

    # Construct the prompts for the model, now asking for instructions
    system_prompt = (
        "You are an expert nutritionist and chef specializing in creating meal plans "
        "for specific dietary needs. Your task is to generate creative, delicious, and "
        "well-balanced meal ideas including step-by-step instructions. "
        "Return the response *only* in the requested JSON format."
    )
    
    user_prompt = (
        f"Please generate a list of 7 prep-ahead lunch ideas (for one person) and "
        f"7 quick-cook dinner ideas (for two people). For each meal, provide the name, "
        f"a list of ingredients, and clear, step-by-step cooking instructions. "
        f"The meals must be compliant with the following dietary requirements: '{dietary_prefs}'. "
        f"Focus on high-protein, meat-inclusive meals. Ensure variety across the suggestions."
    )

    payload = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": json_schema
        }
    }

    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        response_json = response.json()
        json_string = response_json['candidates'][0]['content']['parts'][0]['text']
        generated_meals = json.loads(json_string)
        return generated_meals
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed: {e}")
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        st.error(f"Failed to parse the API response. The response might not be in the expected format. Error: {e}")
        return None

def get_random_meal(meal_type, existing_meal=None):
    """Gets a random meal from the generated pool, ensuring it's not the same as the existing one."""
    if 'generated_meals' not in st.session_state or not st.session_state.generated_meals:
        return {'name': "Generate a meal plan first!", 'ingredients': [], 'instructions': ''}
        
    meal_list = st.session_state.generated_meals.get(meal_type, [])
    if not meal_list:
        return {'name': "No meals found.", 'ingredients': [], 'instructions': ''}
    
    eligible_meals = [m for m in meal_list if m['name'] != (existing_meal['name'] if existing_meal else None)]
    if not eligible_meals:
        return random.choice(meal_list)
        
    return random.choice(eligible_meals)

def generate_shopping_list(meal_plan, pantry_items):
    """Generates a shopping list by aggregating all ingredients and subtracting pantry items."""
    required_items = {}
    pantry_set = {item.strip().lower() for item in pantry_items}

    for day_meals in meal_plan.values():
        for meal in day_meals.values():
            if not meal or 'ingredients' not in meal:
                continue
            for ingredient in meal['ingredients']:
                item_name = ingredient['item'].strip().lower()
                if item_name in pantry_set:
                    continue
                key = (item_name, ingredient['unit'])
                if key in required_items:
                    required_items[key] += ingredient['quantity']
                else:
                    required_items[key] = ingredient['quantity']
    
    shopping_list_str = ""
    if not required_items:
        return "You have everything you need!"
        
    for (item, unit), quantity in sorted(required_items.items()):
        unit_str = unit + 's' if quantity > 1 and len(unit) > 1 else unit
        shopping_list_str += f"- {item.title()}: {quantity} {unit_str}\n"
        
    return shopping_list_str

# --- STREAMLIT APP ---

def main():
    st.set_page_config(page_title="Weekly Meal Planner", layout="wide")

    if 'meal_plan' not in st.session_state:
        st.session_state.meal_plan = {}
    if 'pantry_items' not in st.session_state:
        st.session_state.pantry_items = ["Olive Oil", "Salt", "Black Pepper", "Garlic", "Onion Powder"]
    if 'shopping_list' not in st.session_state:
        st.session_state.shopping_list = ""
    if 'generated_meals' not in st.session_state:
        st.session_state.generated_meals = None

    with st.sidebar:
        st.title("🍽️ Meal Plan Generator")
        st.write("Set your preferences and generate a weekly meal plan.")
        st.header("Customization")
        dietary_prefs = st.text_input(
            "Dietary Preferences & Allergens",
            "gluten-free, low-acid, no nuts, high-protein, meat-focused",
            help="Enter your dietary needs. Be as specific as possible."
        )
        days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        selected_days = st.multiselect(
            "Which days do you need a plan for?",
            options=days_of_week,
            default=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        )

        if st.button("Generate Full Meal Plan", type="primary"):
            with st.spinner("🧠 Gemini is creating your personalized meal plan..."):
                st.session_state.generated_meals = generate_meals_with_gemini(dietary_prefs, selected_days)
            if st.session_state.generated_meals:
                st.session_state.meal_plan = {}
                for day in selected_days:
                    st.session_state.meal_plan[day] = {
                        'Lunch': get_random_meal('Lunch'),
                        'Dinner': get_random_meal('Dinner')
                    }
                st.session_state.shopping_list = ""
                st.success("New meal plan generated!")
            else:
                st.error("Could not generate a meal plan. Please try again.")

    st.title("Your Weekly Meal Plan")

    if not st.session_state.meal_plan:
        st.info("Click 'Generate Full Meal Plan' in the sidebar to start.")
    else:
        for day, meals in st.session_state.meal_plan.items():
            st.subheader(f"📅 {day}")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#####  lunchtime 🥪 (Prep-Ahead)")
                if meals['Lunch']:
                    with st.expander(f"**{meals['Lunch']['name']}**"):
                        st.markdown("**Ingredients:**")
                        for ing in meals['Lunch']['ingredients']:
                            st.markdown(f"- {ing['item']}: {ing['quantity']} {ing['unit']}")
                        st.markdown("**Instructions:**")
                        st.write(meals['Lunch']['instructions'])
                        if st.button("Regenerate Lunch", key=f"regen_lunch_{day}"):
                            st.session_state.meal_plan[day]['Lunch'] = get_random_meal('Lunch', meals['Lunch'])
                            st.session_state.shopping_list = ""
                            st.rerun()

            with col2:
                st.markdown("##### Evening Meal 🍝 (Quick Cook)")
                if meals['Dinner']:
                    with st.expander(f"**{meals['Dinner']['name']}**"):
                        st.markdown("**Ingredients:**")
                        for ing in meals['Dinner']['ingredients']:
                            st.markdown(f"- {ing['item']}: {ing['quantity']} {ing['unit']}")
                        st.markdown("**Instructions:**")
                        st.write(meals['Dinner']['instructions'])
                        if st.button("Regenerate Dinner", key=f"regen_dinner_{day}"):
                            st.session_state.meal_plan[day]['Dinner'] = get_random_meal('Dinner', meals['Dinner'])
                            st.session_state.shopping_list = ""
                            st.rerun()
            st.divider()

    if st.session_state.meal_plan:
        st.title("🛒 Shopping & Pantry")
        pantry_col, shopping_col = st.columns(2)
        with pantry_col:
            st.subheader("Pantry Items")
            pantry_text = st.text_area(
                "Your Pantry:", value="\n".join(st.session_state.pantry_items), height=250, label_visibility="collapsed"
            )
            if st.button("Update Pantry List"):
                st.session_state.pantry_items = [item.strip() for item in pantry_text.split('\n') if item.strip()]
                st.session_state.shopping_list = ""
                st.success("Pantry updated!")
        
        with shopping_col:
            st.subheader("Generated Shopping List")
            if st.button("Generate Shopping List", type="primary"):
                st.session_state.shopping_list = generate_shopping_list(
                    st.session_state.meal_plan, st.session_state.pantry_items
                )
            if st.session_state.shopping_list:
                st.text_area("To Buy:", value=st.session_state.shopping_list, height=250, label_visibility="collapsed")
            else:
                st.info("Click 'Generate Shopping List' after finalizing your meal plan.")

if __name__ == "__main__":
    main()

