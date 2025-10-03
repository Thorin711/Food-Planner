import streamlit as st
import random
import json
import requests

# --- HELPER FUNCTIONS ---

def generate_meals_with_gemini(dietary_prefs, dinner_settings):
    """
    Calls the Gemini API to generate pools of meal ideas based on user preferences,
    including separate pools for different dinner styles if requested.
    """
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        st.error("GEMINI_API_KEY not found. Please add it to your .streamlit/secrets.toml file.")
        return None
        
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={api_key}"

    # --- Dynamic JSON Schema and Prompt Construction ---
    json_schema_properties = {
        "Lunch": {
            "type": "ARRAY",
            "description": "A list of 7 diverse, prep-ahead lunch ideas for one person.",
            "items": {"type": "OBJECT", "properties": {"name": {"type": "STRING"}, "ingredients": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"item": {"type": "STRING"}, "quantity": {"type": "NUMBER"}, "unit": {"type": "STRING"}}, "required": ["item", "quantity", "unit"]}}, "instructions": {"type": "STRING"}}, "required": ["name", "ingredients", "instructions"]}
        }
    }
    required_properties = ["Lunch"]
    dinner_prompt_parts = []

    # Check if any day needs a "Quick Cook" dinner
    if any(d['plan'] and d['style'] == "Quick Cook (<30 mins)" for d in dinner_settings.values()):
        json_schema_properties["QuickDinner"] = {
            "type": "ARRAY", "description": "A list of 7 diverse, quick-cook (under 30 mins) dinner ideas for two people.",
            "items": {"type": "OBJECT", "properties": {"name": {"type": "STRING"}, "ingredients": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"item": {"type": "STRING"}, "quantity": {"type": "NUMBER"}, "unit": {"type": "STRING"}}, "required": ["item", "quantity", "unit"]}}, "instructions": {"type": "STRING"}}, "required": ["name", "ingredients", "instructions"]}
        }
        required_properties.append("QuickDinner")
        dinner_prompt_parts.append("a list of 7 quick-cook (under 30 minutes) dinner ideas for two people")

    # Check if any day needs a "Full Cook" dinner
    if any(d['plan'] and d['style'] == "Full Cook (longer prep)" for d in dinner_settings.values()):
        json_schema_properties["FullDinner"] = {
            "type": "ARRAY", "description": "A list of 7 diverse, 'full cook' (longer prep) dinner ideas for two people.",
            "items": {"type": "OBJECT", "properties": {"name": {"type": "STRING"}, "ingredients": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"item": {"type": "STRING"}, "quantity": {"type": "NUMBER"}, "unit": {"type": "STRING"}}, "required": ["item", "quantity", "unit"]}}, "instructions": {"type": "STRING"}}, "required": ["name", "ingredients", "instructions"]}
        }
        required_properties.append("FullDinner")
        dinner_prompt_parts.append("a list of 7 'full cook' (more involved, longer prep) dinner ideas for two people")

    json_schema = {"type": "OBJECT", "properties": json_schema_properties, "required": list(set(required_properties))}
    
    dinner_prompt = ""
    if dinner_prompt_parts:
        dinner_prompt = f"Also, please generate { ' and '.join(dinner_prompt_parts) }."

    system_prompt = "You are an expert chef specializing in creating meal plans for specific dietary needs. Generate creative, delicious meal ideas with step-by-step instructions. Return the response *only* in the requested JSON format."
    user_prompt = (
        f"Please generate a list of 7 prep-ahead lunch ideas for one person. {dinner_prompt} "
        f"For each meal, provide the name, a list of ingredients, and clear instructions. "
        f"The meals must comply with these dietary requirements: '{dietary_prefs}'. "
        f"Focus on high-protein, meat-inclusive meals."
    )

    payload = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": json_schema}
    }

    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        response_json = response.json()
        json_string = response_json['candidates'][0]['content']['parts'][0]['text']
        return json.loads(json_string)
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed: {e}")
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        st.error(f"Failed to parse API response: {e}")
        return None

def get_random_meal(meal_type, existing_meals=None):
    if 'generated_meals' not in st.session_state or not st.session_state.generated_meals:
        return {'name': "Generate a meal plan first!", 'ingredients': [], 'instructions': ''}
    
    meal_list = st.session_state.generated_meals.get(meal_type, [])
    if not meal_list:
        return {'name': "No meals found for this style.", 'ingredients': [], 'instructions': ''}
    
    # Ensure existing_meals is a list of names
    existing_names = []
    if existing_meals:
        if isinstance(existing_meals, list):
            existing_names = [m['name'] for m in existing_meals]
        elif isinstance(existing_meals, dict): # Handle single meal object
            existing_names = [existing_meals['name']]

    eligible_meals = [m for m in meal_list if m['name'] not in existing_names]
    
    return random.choice(eligible_meals) if eligible_meals else random.choice(meal_list)

def generate_shopping_list(meal_plan, pantry_items):
    required_items = {}
    pantry_set = {item.strip().lower() for item in pantry_items}
    
    # Process lunches
    for meal in meal_plan.get('Lunches', []):
        for ingredient in meal['ingredients']:
            item_name = ingredient['item'].strip().lower()
            if item_name in pantry_set: continue
            key = (item_name, ingredient['unit'])
            required_items[key] = required_items.get(key, 0) + ingredient['quantity']

    # Process dinners
    for meal in meal_plan.get('Dinners', {}).values():
        if meal:
            for ingredient in meal['ingredients']:
                item_name = ingredient['item'].strip().lower()
                if item_name in pantry_set: continue
                key = (item_name, ingredient['unit'])
                required_items[key] = required_items.get(key, 0) + ingredient['quantity']
                
    if not required_items: return "You have everything you need!"
    shopping_list_str = ""
    for (item, unit), quantity in sorted(required_items.items()):
        unit_str = unit + ('s' if quantity > 1 and len(unit) > 1 else '')
        shopping_list_str += f"- {item.title()}: {quantity} {unit_str}\n"
    return shopping_list_str

# --- STREAMLIT APP ---

def main():
    st.set_page_config(page_title="Weekly Meal Planner", layout="wide")
    
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {
            width: 400px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    for key, default in [('meal_plan', {}), ('pantry_items', ["Olive Oil", "Salt", "Black Pepper", "Garlic", "Onion Powder"]), ('shopping_list', ""), ('generated_meals', None), ('dinner_settings', {})]:
        if key not in st.session_state:
            st.session_state[key] = default

    with st.sidebar:
        st.title("🍽️ Meal Plan Generator")
        st.write("Set your preferences and generate a weekly meal plan.")
        st.header("Customization")
        dietary_prefs = st.text_input("Dietary Preferences & Allergens", "gluten-free, low-acid, no nuts, high-protein, meat-focused")
        
        st.header("Select Days to Plan")
        days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        default_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        
        selected_days_list = []
        for day in days_of_week:
            col1, col2 = st.columns([2, 3])
            with col1: st.markdown(f"**{day}**")
            with col2:
                choice = st.radio(label=f"Plan for {day}?", options=["Plan", "Skip"], index=0 if day in default_days else 1, horizontal=True, key=f"radio_{day}", label_visibility="collapsed")
            if choice == "Plan":
                selected_days_list.append(day)
        
        selected_days = selected_days_list

        if any(day in selected_days for day in days_of_week):
            st.header("Evening Meal Settings")
            for day in selected_days:
                if day not in st.session_state.dinner_settings:
                    st.session_state.dinner_settings[day] = {'plan': True, 'style': "Quick Cook (<30 mins)"}
                with st.expander(day, expanded=False):
                    plan_dinner_for_day = st.checkbox("Plan dinner?", value=st.session_state.dinner_settings[day]['plan'], key=f"plan_{day}")
                    st.session_state.dinner_settings[day]['plan'] = plan_dinner_for_day
                    if plan_dinner_for_day:
                        dinner_style_for_day = st.radio("Style:", ["Quick Cook (<30 mins)", "Full Cook (longer prep)"], index=0 if st.session_state.dinner_settings[day]['style'] == "Quick Cook (<30 mins)" else 1, horizontal=True, key=f"style_{day}")
                        st.session_state.dinner_settings[day]['style'] = dinner_style_for_day
        
        if st.button("Generate Full Meal Plan", type="primary"):
            with st.spinner("🧠 Gemini is creating your personalized meal plan..."):
                st.session_state.generated_meals = generate_meals_with_gemini(dietary_prefs, st.session_state.dinner_settings)
            
            if st.session_state.generated_meals:
                st.session_state.meal_plan = {'Lunches': [], 'Dinners': {}}
                # Populate Lunches
                for _ in selected_days:
                    st.session_state.meal_plan['Lunches'].append(get_random_meal('Lunch', st.session_state.meal_plan['Lunches']))
                
                # Populate Dinners
                for day in selected_days:
                    day_settings = st.session_state.dinner_settings.get(day, {'plan': False})
                    if day_settings['plan']:
                        meal_pool = "QuickDinner" if day_settings['style'] == "Quick Cook (<30 mins)" else "FullDinner"
                        st.session_state.meal_plan['Dinners'][day] = get_random_meal(meal_pool)
                st.session_state.shopping_list = ""
                st.success("New meal plan generated!")
            else:
                st.error("Could not generate a meal plan. Please try again.")

    st.title("Your Weekly Meal Plan")

    if not st.session_state.meal_plan:
        st.info("Click 'Generate Full Meal Plan' in the sidebar to start.")
    else:
        # --- LUNCH PREP SECTION ---
        st.header("Weekday Lunch Prep 🥪")
        st.write("All your prep-ahead lunches for the week, ready for your weekend cooking session.")
        lunches = st.session_state.meal_plan.get('Lunches', [])
        if lunches:
            for i, lunch in enumerate(lunches):
                with st.expander(f"**Lunch Option {i+1}: {lunch['name']}**"):
                    st.markdown("**Ingredients:**")
                    for ing in lunch['ingredients']:
                        st.markdown(f"- {ing['item']}: {ing['quantity']} {ing['unit']}")
                    st.markdown("**Instructions:**")
                    st.write(lunch['instructions'])
                    if st.button("Regenerate Lunch", key=f"regen_lunch_{i}"):
                        st.session_state.meal_plan['Lunches'][i] = get_random_meal('Lunch', st.session_state.meal_plan['Lunches'])
                        st.session_state.shopping_list = ""
                        st.rerun()
        st.divider()

        # --- EVENING MEALS SECTION ---
        st.header("Evening Meals 🍝")
        st.write("Your fresh-cook evening meals, organized by day.")
        dinners = st.session_state.meal_plan.get('Dinners', {})
        for day in selected_days:
            dinner = dinners.get(day)
            if dinner:
                st.subheader(f"📅 {day}")
                with st.expander(f"**{dinner['name']}**"):
                    st.markdown("**Ingredients:**")
                    for ing in dinner['ingredients']:
                        st.markdown(f"- {ing['item']}: {ing['quantity']} {ing['unit']}")
                    st.markdown("**Instructions:**")
                    st.write(dinner['instructions'])
                    if st.button("Regenerate Dinner", key=f"regen_dinner_{day}"):
                        day_settings = st.session_state.dinner_settings.get(day)
                        meal_pool = "QuickDinner" if day_settings['style'] == "Quick Cook (<30 mins)" else "FullDinner"
                        st.session_state.meal_plan['Dinners'][day] = get_random_meal(meal_pool, dinner)
                        st.session_state.shopping_list = ""
                        st.rerun()

    if st.session_state.meal_plan:
        st.title("🛒 Shopping & Pantry")
        pantry_col, shopping_col = st.columns(2)
        with pantry_col:
            st.subheader("Pantry Items")
            pantry_text = st.text_area("Your Pantry:", value="\n".join(st.session_state.pantry_items), height=250, label_visibility="collapsed")
            if st.button("Update Pantry List"):
                st.session_state.pantry_items = [item.strip() for item in pantry_text.split('\n') if item.strip()]
                st.session_state.shopping_list = ""
                st.success("Pantry updated!")
        with shopping_col:
            st.subheader("Generated Shopping List")
            if st.button("Generate Shopping List", type="primary"):
                st.session_state.shopping_list = generate_shopping_list(st.session_state.meal_plan, st.session_state.pantry_items)
            if st.session_state.shopping_list:
                st.text_area("To Buy:", value=st.session_state.shopping_list, height=250, label_visibility="collapsed")
            else:
                st.info("Click 'Generate Shopping List' after finalizing your meal plan.")

if __name__ == "__main__":
    main()