import streamlit as st
import random
import json
import requests

# --- HELPER FUNCTIONS ---

def generate_meals_with_gemini(dietary_prefs, dinner_settings, num_lunches):
    """
    Calls the Gemini API to generate a consolidated prep plan and daily assembly instructions for lunches,
    plus separate pools for different dinner styles if requested.
    """
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        st.error("GEMINI_API_KEY not found. Please add it to your .streamlit/secrets.toml file.")
        return None
        
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={api_key}"

    # --- Dynamic JSON Schema and Prompt Construction ---
    json_schema_properties = {
        "LunchPrep": {
            "type": "OBJECT",
            "description": "A consolidated plan for prepping lunch components over the weekend.",
            "properties": {
                "ingredients": {"type": "ARRAY", "description": "A complete, aggregated list of all ingredients needed for all lunches.", "items": {"type": "OBJECT", "properties": {"item": {"type": "STRING"}, "quantity": {"type": "NUMBER"}, "unit": {"type": "STRING"}}, "required": ["item", "quantity", "unit"]}},
                "prep_instructions": {"type": "STRING", "description": "A single, consolidated set of instructions for preparing all lunch components in one session. Each step should be on a new line."}
            },
            "required": ["ingredients", "prep_instructions"]
        },
        "LunchAssembly": {
            "type": "ARRAY",
            "description": f"A list of {num_lunches} unique lunch assembly plans for each day.",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING", "description": "A creative name for the daily assembled lunch, e.g., 'Chicken & Quinoa Power Bowl'."},
                    "assembly_instructions": {"type": "STRING", "description": "Simple, step-by-step instructions to combine prepped components. Each step should be on a new line."}
                },
                "required": ["name", "assembly_instructions"]
            }
        }
    }
    required_properties = ["LunchPrep", "LunchAssembly"]
    dinner_prompt_parts = []

    # Add dinner sections to schema if needed
    if any(d['plan'] and d['style'] == "Quick Cook (<30 mins)" for d in dinner_settings.values()):
        json_schema_properties["QuickDinner"] = {"type": "ARRAY", "description": "A list of 7 diverse, quick-cook dinner ideas.", "items": {"type": "OBJECT", "properties": {"name": {"type": "STRING"}, "ingredients": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"item": {"type": "STRING"}, "quantity": {"type": "NUMBER"}, "unit": {"type": "STRING"}},"required": ["item", "quantity", "unit"]}}, "instructions": {"type": "STRING", "description": "Step-by-step cooking instructions. Each step on a new line."}}, "required": ["name", "ingredients", "instructions"]}}
        required_properties.append("QuickDinner")
        dinner_prompt_parts.append("a list of 7 quick-cook (under 30 minutes) dinner ideas")

    if any(d['plan'] and d['style'] == "Full Cook (longer prep)" for d in dinner_settings.values()):
        json_schema_properties["FullDinner"] = {"type": "ARRAY", "description": "A list of 7 diverse, 'full cook' dinner ideas.", "items": {"type": "OBJECT", "properties": {"name": {"type": "STRING"}, "ingredients": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"item": {"type": "STRING"}, "quantity": {"type": "NUMBER"}, "unit": {"type": "STRING"}},"required": ["item", "quantity", "unit"]}}, "instructions": {"type": "STRING", "description": "Step-by-step cooking instructions. Each step on a new line."}}, "required": ["name", "ingredients", "instructions"]}}
        required_properties.append("FullDinner")
        dinner_prompt_parts.append("a list of 7 'full cook' (more involved) dinner ideas")

    json_schema = {"type": "OBJECT", "properties": json_schema_properties, "required": list(set(required_properties))}
    
    dinner_prompt = f"Also, please generate { ' and '.join(dinner_prompt_parts) } for two people." if dinner_prompt_parts else ""

    system_prompt = "You are an expert meal prep chef. Your task is to create a smart, efficient weekly meal plan. For lunches, you must first design a set of common, preppable components, provide a single set of instructions to prepare them all at once, and then provide simple daily instructions to assemble them into unique meals. For dinners, provide full recipes. Ensure each instruction step is on a new line. Adhere strictly to the user's dietary needs and return the response *only* in the requested JSON format."
    user_prompt = (
        f"Create a meal plan for one person based on these dietary requirements: '{dietary_prefs}'.\n\n"
        f"LUNCH PLAN (for {num_lunches} days):\n"
        f"1.  First, create a consolidated 'LunchPrep' plan. This should include an aggregated list of all ingredients for the lunches, and one single set of cohesive instructions for prepping all components together during a weekend session (e.g., cook all grains, roast all vegetables, prepare all proteins).\n"
        f"2.  Then, create {num_lunches} unique 'LunchAssembly' plans. Each should have a creative name and simple instructions for assembling the prepped components into a meal each day.\n\n"
        f"DINNER PLAN:\n"
        f"{dinner_prompt}"
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

def format_instructions(instructions_text):
    """Formats a block of text into a numbered markdown list."""
    if not instructions_text or not isinstance(instructions_text, str):
        return "No instructions provided."
    steps = [f"{i+1}. {step.strip()}" for i, step in enumerate(instructions_text.strip().split('\n')) if step.strip()]
    return "\n".join(steps)

def get_random_meal(meal_type, existing_meals=None):
    if 'generated_meals' not in st.session_state or not st.session_state.generated_meals:
        return {'name': "Generate plan first!", 'ingredients': [], 'instructions': ''}
    meal_list = st.session_state.generated_meals.get(meal_type, [])
    if not meal_list:
        return {'name': "No meals for this style.", 'ingredients': [], 'instructions': ''}
    existing_names = [m['name'] for m in (existing_meals or [])]
    eligible_meals = [m for m in meal_list if m['name'] not in existing_names]
    return random.choice(eligible_meals) if eligible_meals else random.choice(meal_list)

def generate_shopping_list(meal_plan, pantry_items):
    required_items = {}
    pantry_set = {item.strip().lower() for item in pantry_items}
    
    # Process lunch prep ingredients
    if 'LunchPrep' in meal_plan and 'ingredients' in meal_plan['LunchPrep']:
        for ingredient in meal_plan['LunchPrep']['ingredients']:
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
        [data-testid="stSidebar"] { width: 400px !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    for key, default in [('meal_plan', {}), ('pantry_items', ["Olive Oil", "Salt", "Black Pepper", "Garlic", "Onion Powder"]), ('shopping_list', ""), ('generated_meals', None), ('dinner_settings', {})]:
        if key not in st.session_state: st.session_state[key] = default

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
            if choice == "Plan": selected_days_list.append(day)
        selected_days = selected_days_list

        if selected_days:
            st.header("Evening Meal Settings")
            for day in selected_days:
                if day not in st.session_state.dinner_settings: st.session_state.dinner_settings[day] = {'plan': True, 'style': "Quick Cook (<30 mins)"}
                with st.expander(day, expanded=False):
                    st.session_state.dinner_settings[day]['plan'] = st.checkbox("Plan dinner?", value=st.session_state.dinner_settings[day]['plan'], key=f"plan_{day}")
                    if st.session_state.dinner_settings[day]['plan']:
                        st.session_state.dinner_settings[day]['style'] = st.radio("Style:", ["Quick Cook (<30 mins)", "Full Cook (longer prep)"], index=0 if st.session_state.dinner_settings[day]['style'] == "Quick Cook (<30 mins)" else 1, horizontal=True, key=f"style_{day}")
        
        if st.button("Generate Full Meal Plan", type="primary"):
            if not selected_days:
                st.warning("Please select at least one day to plan for.")
            else:
                with st.spinner("🧠 Gemini is creating your smart meal prep plan..."):
                    st.session_state.generated_meals = generate_meals_with_gemini(dietary_prefs, st.session_state.dinner_settings, len(selected_days))
                
                if st.session_state.generated_meals:
                    st.session_state.meal_plan = {
                        'LunchPrep': st.session_state.generated_meals.get('LunchPrep'),
                        'Lunches': st.session_state.generated_meals.get('LunchAssembly', []),
                        'Dinners': {}
                    }
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
        st.header("Weekend Lunch Prep 🧑‍🍳")
        lunch_prep = st.session_state.meal_plan.get('LunchPrep')
        if lunch_prep:
            with st.container(border=True):
                st.subheader("Consolidated Prep Instructions")
                st.markdown(format_instructions(lunch_prep['prep_instructions']))
                if st.button("Regenerate Entire Lunch Plan"):
                    with st.spinner("🧠 Gemini is rethinking your lunch prep..."):
                        new_meals = generate_meals_with_gemini(dietary_prefs, st.session_state.dinner_settings, len(selected_days))
                        if new_meals:
                            st.session_state.generated_meals.update({'LunchPrep': new_meals.get('LunchPrep'), 'LunchAssembly': new_meals.get('LunchAssembly')})
                            st.session_state.meal_plan.update({'LunchPrep': new_meals.get('LunchPrep'), 'Lunches': new_meals.get('LunchAssembly', [])})
                            st.session_state.shopping_list = ""
                            st.success("Lunch plan regenerated!")
                            st.rerun()
                        else:
                            st.error("Failed to regenerate lunches.")

        st.divider()

        # --- DAILY ASSEMBLY & EVENING MEALS ---
        st.header("Daily Meals 🍽️")
        lunches = st.session_state.meal_plan.get('Lunches', [])
        dinners = st.session_state.meal_plan.get('Dinners', {})
        
        for i, day in enumerate(selected_days):
            st.subheader(f"📅 {day}")
            lunch = lunches[i] if i < len(lunches) else None
            dinner = dinners.get(day)
            
            # Render Lunch section
            st.markdown("#####  lunchtime 🥪 (Assembly)")
            if lunch:
                with st.expander(f"**{lunch['name']}**"):
                    st.markdown(format_instructions(lunch['assembly_instructions']))

            # Render Dinner section if it exists for the day
            if dinner:
                st.markdown("##### Evening Meal 🍝 (Cook Fresh)")
                with st.expander(f"**{dinner['name']}**"):
                    st.markdown("**Ingredients:**")
                    ingredients_text = ""
                    for ing in dinner['ingredients']:
                        ingredients_text += f"- {ing['item']}: {ing['quantity']} {ing['unit']}\n"
                    st.markdown(ingredients_text)
                    
                    st.markdown("**Instructions:**")
                    st.markdown(format_instructions(dinner['instructions']))
                    if st.button("Regenerate Dinner", key=f"regen_dinner_{day}"):
                        day_settings = st.session_state.dinner_settings.get(day)
                        meal_pool = "QuickDinner" if day_settings['style'] == "Quick Cook (<30 mins)" else "FullDinner"
                        st.session_state.meal_plan['Dinners'][day] = get_random_meal(meal_pool, dinner)
                        st.session_state.shopping_list = ""
                        st.rerun()
            
            st.divider()

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

