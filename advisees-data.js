(function () {
  const DEFAULT_ADVISEES_DATA_URL = "data/advisees.json";

  function getAdviseesDataUrl() {
    return window.ADVISEES_DATA_URL || DEFAULT_ADVISEES_DATA_URL;
  }

  function studentToLegacyRow(student) {
    return {
      "屆次": student.cohort || "",
      "入學年度": student.admissionYear || "",
      "學生姓名": student.name || "",
      "論文類型": student.thesisType || "",
      "指導老師": student.advisor || "",
      "論文題目": student.thesisTitle || "",
      "Advised": student.advised ? "1" : "",
      "Proposal": student.proposal ? "1" : "",
      "Final": student.final ? "1" : "",
      "工作": student.job || "",
      "類型": student.workType || "",
      "url": student.url || "",
    };
  }

  function adviseesPayloadToRows(payload) {
    if (Array.isArray(payload)) {
      return payload;
    }
    const students = Array.isArray(payload.students) ? payload.students : [];
    return students.map(studentToLegacyRow);
  }

  async function fetchAdviseesPayload(options = {}) {
    const response = await fetch(getAdviseesDataUrl(), {
      cache: options.cache || "no-store",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  }

  async function loadAdviseesData(options = {}) {
    const payload = await fetchAdviseesPayload(options);
    return adviseesPayloadToRows(payload);
  }

  window.getAdviseesDataUrl = getAdviseesDataUrl;
  window.fetchAdviseesPayload = fetchAdviseesPayload;
  window.adviseesPayloadToRows = adviseesPayloadToRows;
  window.loadAdviseesData = loadAdviseesData;
})();
