---
id: course-basic
description: Course search, registration, and schedule management
whenToUse: When an agent needs to find courses, check prerequisites, or register/drop courses
tags:
  - course
  - registration
  - academic
  - schedule
---

## Course Management

### Finding Courses
1. Use `course.search` with keywords (topic, course name, or code)
2. Optionally filter by `department` to narrow results
3. Note the `course_id` from search results for further actions

### Checking Course Details
1. Use `course.get_details` to see full information: schedule, instructor, credits, capacity
2. Use `course.check_prerequisites` to verify you meet the requirements before attempting registration
3. Use `course.check_conflicts` to ensure the course fits your current schedule

### Registration Workflow
1. Search for the course
2. Check prerequisites — registration will fail if unmet
3. Check schedule conflicts — overlapping courses cannot both be registered
4. Use `course.register` to enroll
5. Verify success by checking the schedule with `calendar.get_schedule`

### Dropping a Course
1. Use `course.drop` with the `course_id`
2. Be aware of drop deadlines — late drops may have academic penalties

### Tips
- Always check prerequisites before registering — saves a failed attempt
- Check conflicts before registering — the system rejects overlapping schedules
- When searching, try both specific codes ("CS101") and general topics ("machine learning")
- After registering, verify the course appears in your schedule
