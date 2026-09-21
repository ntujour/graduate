(function () {
  const DEFAULT_COURSES_DATA_URL = "data/courses.json";

  function getCoursesDataUrl() {
    return window.COURSES_DATA_URL || DEFAULT_COURSES_DATA_URL;
  }

  function normalizeCourse(course, semesters) {
    const normalized = {
      ...course,
      credit: course.credit == null ? "" : String(course.credit),
    };

    semesters.forEach((semester) => {
      normalized[semester] = course.offerings && course.offerings[semester] ? "1" : "x";
    });

    return normalized;
  }

  function coursesPayloadToRows(payload) {
    if (Array.isArray(payload)) {
      return payload;
    }

    const semesters = Array.isArray(payload.semesters) ? payload.semesters : [];
    const courses = Array.isArray(payload.courses) ? payload.courses : [];
    return courses.map((course) => normalizeCourse(course, semesters));
  }

  async function fetchCoursesPayload(options = {}) {
    const response = await fetch(getCoursesDataUrl(), {
      cache: options.cache || "no-store",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  }

  async function loadCoursesData(options = {}) {
    const payload = await fetchCoursesPayload(options);
    return coursesPayloadToRows(payload);
  }

  window.getCoursesDataUrl = getCoursesDataUrl;
  window.fetchCoursesPayload = fetchCoursesPayload;
  window.coursesPayloadToRows = coursesPayloadToRows;
  window.loadCoursesData = loadCoursesData;
})();
