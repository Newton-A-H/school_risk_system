from datetime import datetime, timedelta


def _normalize_text(value):
    return (value or "").strip()


def _build_priority(risk_level):
    if risk_level == "High Risk":
        return {
            "priority": "Immediate",
            "deadline_label": "Within 24 hours",
            "badge_class": "text-bg-danger",
            "days": 1,
            "alert_message": "Immediate intervention is recommended for this learner.",
        }
    if risk_level == "Medium Risk":
        return {
            "priority": "Moderate",
            "deadline_label": "Within 7 days",
            "badge_class": "text-bg-warning",
            "days": 7,
            "alert_message": "Targeted support should be scheduled soon.",
        }
    return {
        "priority": "Routine",
        "deadline_label": "Routine monitoring",
        "badge_class": "text-bg-success",
        "days": 14,
        "alert_message": "Continue monitoring and encouraging consistent performance.",
    }


def generate_advisory(risk_level, record, response):
    final_mark = float(record.final_mark or 0)
    coursework_total = float(record.coursework_total or 0)
    exam_mark = float(record.exam_mark or 0)
    attendance_percent = float(record.attendance_percent or 0)
    assignment_mark = float(record.assignment_mark or 0)
    cat_mark = float(record.cat_mark or 0)

    attendance_frequency = _normalize_text(response.attendance_frequency)
    coursework_on_time = _normalize_text(response.coursework_on_time)
    main_challenge = _normalize_text(response.main_challenge)
    early_warning_helpful = _normalize_text(response.early_warning_helpful)
    study_hours_per_week = float(response.study_hours_per_week or 0)

    priority_data = _build_priority(risk_level)
    deadline_date = (datetime.utcnow() + timedelta(days=priority_data["days"])).strftime("%d %b %Y")

    drivers = []
    action_plan = []

    if final_mark < 40:
        drivers.append("Final mark is critically low and shows urgent academic risk.")
        action_plan.append("Schedule an immediate academic support meeting and review all weak subjects.")
    elif final_mark < 50:
        drivers.append("Final mark is below a safe performance level.")
        action_plan.append("Arrange targeted revision support and close weekly follow-up.")
    elif final_mark < 60:
        drivers.append("Final mark is only slightly above risk range and still needs monitoring.")
        action_plan.append("Set short-term academic goals and monitor performance trend.")

    if attendance_percent < 50:
        drivers.append("Attendance is extremely low and likely affecting learning continuity.")
        action_plan.append("Discuss attendance barriers immediately and agree on a strict attendance recovery plan.")
    elif attendance_percent < 75:
        drivers.append("Attendance is below the expected level for healthy academic progress.")
        action_plan.append("Track class attendance weekly and follow up on missed sessions.")

    if coursework_total < 15:
        drivers.append("Coursework performance is weak and may reflect poor preparation or missed submissions.")
        action_plan.append("Review assignment completion and provide structured coursework support.")
    elif coursework_total < 21:
        drivers.append("Coursework is below expected performance and needs improvement.")
        action_plan.append("Create a coursework improvement checklist and monitor completion.")

    if exam_mark < 35:
        drivers.append("Exam performance is weak and suggests poor retention or revision gaps.")
        action_plan.append("Introduce focused revision sessions and exam-practice support.")

    if study_hours_per_week < 5:
        drivers.append("Study time per week is too low to support stable academic progress.")
        action_plan.append("Help the learner build a weekly study timetable with realistic daily targets.")
    elif study_hours_per_week < 10:
        drivers.append("Study time is below an ideal level for consistent improvement.")
        action_plan.append("Increase weekly self-study time and review adherence every week.")

    if attendance_frequency in {"Rarely", "Sometimes"}:
        drivers.append("Self-reported attendance frequency shows inconsistency.")
        action_plan.append("Work with the learner to identify and remove attendance obstacles.")

    if coursework_on_time in {"Rarely", "No", "Late", "Sometimes"}:
        drivers.append("Coursework submission pattern suggests weak time management or disengagement.")
        action_plan.append("Set firm assignment deadlines with regular lecturer follow-up.")

    if main_challenge and main_challenge != "None":
        drivers.append(f"The learner reported a major challenge: {main_challenge}.")
        action_plan.append(f"Address the reported challenge directly through referral, guidance, or practical support.")

    if early_warning_helpful == "Yes":
        drivers.append("The learner has indicated that early warning support would be helpful.")
        action_plan.append("Provide proactive check-ins and early support before performance drops further.")

    if not drivers:
        drivers.append("Current data shows no major immediate academic risk driver.")
    if not action_plan:
        action_plan.append("Continue routine monitoring and reinforce good study habits.")

    # Keep the lists focused
    drivers = drivers[:5]
    action_plan = action_plan[:5]

    if risk_level == "High Risk":
        summary = (
            "High risk detected. Immediate intervention is required, with strong attention to "
            "attendance, academic performance, and the learner's reported barriers."
        )
    elif risk_level == "Medium Risk":
        summary = (
            "Medium risk detected. Early targeted support is recommended to prevent further decline."
        )
    else:
        summary = (
            "Low risk detected. Maintain current performance through routine monitoring and encouragement."
        )

    return {
        "summary": summary,
        "priority": priority_data["priority"],
        "deadline_label": priority_data["deadline_label"],
        "deadline_date": deadline_date,
        "badge_class": priority_data["badge_class"],
        "alert_message": priority_data["alert_message"],
        "drivers": drivers,
        "action_plan": action_plan,
    }