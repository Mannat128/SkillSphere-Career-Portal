export function buildUnansweredQuestionParams(filters = {}) {
  const rawFrequency = Number(filters.min_frequency);
  const minFrequency = Number.isInteger(rawFrequency) && rawFrequency >= 1 ? rawFrequency : 1;
  return {
    ...(filters.language ? { language: filters.language } : {}),
    min_frequency: minFrequency,
  };
}

export async function loadUnansweredQuestions(apiClient, filters) {
  const { data } = await apiClient.get('/assistant/admin/unanswered', {
    params: buildUnansweredQuestionParams(filters),
  });
  return Array.isArray(data) ? data : [];
}
