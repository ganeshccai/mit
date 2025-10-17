from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import os

app = Flask(__name__)

firebase_admin.initialize_app()
db = firestore.client()


# Get unique categories
def handle_get_categories():
    docs = db.collection("MIT_courses").stream()
    categories = set(
        doc.to_dict().get("category", "").strip()
        for doc in docs
        if doc.to_dict().get("category")
    )
    chips = [{"text": cat} for cat in sorted(categories)]
    return rich_chip_response("Select a category:", chips)


# Get departments by category
def handle_get_departments(category):
    print("Dialogflow category parameter:", category)
    docs = db.collection("MIT_courses").stream()
    all_categories = set(
        doc.to_dict().get("category", "").strip()
        for doc in docs
        if doc.to_dict().get("category")
    )
    print("All Firestore categories:", all_categories)

    # Now do the actual query
    docs = db.collection("MIT_courses").where("category", "==", category).stream()
    departments = set(
        doc.to_dict().get("department", "").strip()
        for doc in docs
        if doc.to_dict().get("department")
    )
    print("Departments found:", departments)

    if not departments:
        return jsonify(
            {"fulfillmentText": f"No departments found for category: {category}"}
        )

    chips = [{"text": dept} for dept in sorted(departments)]
    return rich_chip_response(f"Select the department:", chips)


# Get courses by category & department
def handle_get_courses(category, department):
    print("Dialogflow category:", category)
    docs = (
        db.collection("MIT_courses")
        .where("category", "==", category)
        .where("department", "==", department)
        .stream()
    )

    course_names = []
    course_details = {}
    for doc in docs:
        data = doc.to_dict()
        course_name = data.get("course_name")  # This is "Pgcm Business Analytics"
        course_name_lower = data.get("course_name_lower", course_name.lower())
        if course_name:
            course_names.append(course_name)
            course_details[course_name_lower] = data  # Store data by lowercase name

    if not course_names:
        return jsonify(
            {"fulfillmentText": f"No courses found under {category} > {department}"}
        )

    selected_course = (
        request.get_json()["queryResult"]["parameters"]
        .get("course_name", "")
        .strip()
        .lower()
    )

    if selected_course and selected_course in course_details:
        # Show only titles as chips/buttons
        detail_titles = [
            {"text": "Eligibility", "value": {"detail_type": "eligibility"}},
            {"text": "Duration", "value": {"detail_type": "duration"}},
            {"text": "Fee", "value": {"detail_type": "fee"}},
            {"text": "Features", "value": {"detail_type": "features"}},
            {"text": "Syllabus", "value": {"detail_type": "syllabus"}},
        ]
        # Fetch course description using the stored data
        data = course_details[selected_course]
        description = data.get("description", "No description available.")

        return jsonify(
            {
                "fulfillmentMessages": [
                    {"text": {"text": [description]}},
                    {
                        "payload": {
                            "richContent": [
                                [{"type": "chips", "options": detail_titles}]
                            ]
                        }
                    },
                ]
            }
        )
    else:
        # Show course names as chips/buttons for selection (with correct capitalization)
        course_chips = [{"text": name} for name in course_names]
        return jsonify(
            {
                "fulfillmentMessages": [
                    {"text": {"text": [f"Select a course below:"]}},
                    {
                        "payload": {
                            "richContent": [
                                [{"type": "chips", "options": course_chips}]
                            ]
                        }
                    },
                ]
            }
        )


def handle_main_menu():
    chips = [
        {"text": "Courses"},
        # Add more options here if needed
    ]
    return rich_chip_response(
        "Welcome to the Main Menu! Please choose an option:", chips
    )


# 🔹 Rich chip response
def rich_chip_response(text, chips):
    return jsonify(
        {
            "fulfillmentMessages": [
                {"text": {"text": [text]}},
                {"payload": {"richContent": [[{"type": "chips", "options": chips}]]}},
            ]
        }
    )


@app.route("/webhook", methods=["POST"])
def webhook():
    req = request.get_json()
    print("Dialogflow request:", req)
    print("Course name parameter:", req["queryResult"]["parameters"].get("course_name"))
    print("All parameters:", req["queryResult"]["parameters"])
    intent = req["queryResult"]["intent"]["displayName"]

    if intent == "A1-Courses-category":
        return handle_get_categories()
    elif intent == "A2-Courses-department":
        category = req["queryResult"]["parameters"].get("category", "").strip()
        return handle_get_departments(category)
    elif intent == "A3-Courses-course":
        category = req["queryResult"]["parameters"].get("category", "").strip()
        department = req["queryResult"]["parameters"].get("department", "").strip()
        return handle_get_courses(category, department)
    elif intent == "A4-Courses-showcourse":
        category = req["queryResult"]["parameters"].get("category", "").strip()
        department = req["queryResult"]["parameters"].get("department", "").strip()
        return handle_get_courses(category, department)
    elif intent == "A5-Courses_coursedetails":
        course_name = req["queryResult"]["parameters"].get("course_name", "").strip()
        if not course_name:
            for ctx in req["queryResult"].get("outputContexts", []):
                params = ctx.get("parameters", {})
                if "course_name" in params:
                    course_name = params["course_name"]
                    break

        detail_type = (
            req["queryResult"]["parameters"]
            .get("detail_type", "")
            .strip()
            .lower()
            .replace("_", "")
            .replace(" ", "")
        )

        print("DEBUG: course_name:", course_name)
        print("DEBUG: detail_type:", detail_type)

        # Lowercase for Firestore query
        course_name_lower = course_name.lower()
        docs = (
            db.collection("MIT_courses")
            .where("course_name", "==", course_name)
            .stream()
        )
        value = "Not available"
        for doc in docs:
            data = doc.to_dict()
            print("DEBUG: Firestore data:", data)
            # Always use lowercase for field lookup
            field_map = {
                "eligibility": "eligibility",
                "duration": "duration",
                "fee": "fee",
                "features": "features",
                "syllabus": "syllabus",
            }
            field = field_map.get(detail_type)
            print("DEBUG: field used:", field)
            if not field:
                value = "Not available"
            else:
                value = data.get(field, "Not available")
            break

        # Show detail buttons again, now with Main Menu option
        detail_titles = [
            {"text": "Eligibility", "value": {"detail_type": "eligibility"}},
            {"text": "Duration", "value": {"detail_type": "duration"}},
            {"text": "Fee", "value": {"detail_type": "fee"}},
            {"text": "Features", "value": {"detail_type": "features"}},
            {"text": "Syllabus", "value": {"detail_type": "syllabus"}},
            {"text": "Main Menu"},  # Add this line
        ]

        # Set output context to remember course_name for next detail click
        return jsonify(
            {
                "fulfillmentMessages": [
                    {"text": {"text": [f"{value}"]}},
                    {
                        "payload": {
                            "richContent": [
                                [{"type": "chips", "options": detail_titles}]
                            ]
                        }
                    },
                ],
                "outputContexts": [
                    {
                        "name": f"{req['session']}/contexts/course-followup",
                        "lifespanCount": 5,
                        "parameters": {"course_name": course_name},
                    }
                ],
            }
        )

    elif (
        intent == "ShowMainMenuButton"
    ):  # Use a dedicated intent for showing the button
        main_menu_chips = [
            {"text": "Main Menu"},
        ]
        return rich_chip_response("Click below to open Main Menu:", main_menu_chips)
    elif intent == "MainMenu":
        return handle_main_menu()
    else:
        return jsonify({"fulfillmentText": "Sorry, I didn't understand that."})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
