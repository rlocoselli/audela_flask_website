using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using AudelaMobileLight.Models;

namespace AudelaMobileLight.Services;

public sealed class MobileVisualizationService
{
    private readonly HttpClient _httpClient = new()
    {
        Timeout = TimeSpan.FromSeconds(10),
    };

    public async Task<MobileDashboardMetrics> GetDashboardAsync(CancellationToken cancellationToken)
    {
        var payload = await GetFirstAsync<DashboardPayload>("/api/mobile/dashboard", cancellationToken);
        return payload is null
            ? new MobileDashboardMetrics()
            : new MobileDashboardMetrics
            {
                DashboardCount = payload.DashboardCount,
                QueryRunCount = payload.QueryRunCount,
                FinanceEntriesCount = payload.FinanceEntriesCount,
                FinanceNetAmount = payload.FinanceNetAmount,
                LearningModulesCount = payload.LearningModulesCount,
                LearningProgressAvg = payload.LearningProgressAvg,
            };
    }

    public async Task<IReadOnlyList<MobileBiDataSource>> GetBiDataSourcesAsync(CancellationToken cancellationToken)
    {
        var payload = await GetFirstAsync<BiDataSourcePayload>(["/api/mobile/bi/datasources", "/tenant/api/mobile/bi/datasources"], cancellationToken);
        return payload?.Datasources ?? [];
    }

    public async Task<IReadOnlyList<MobileBiDashboardSummary>> GetBiDashboardsAsync(CancellationToken cancellationToken)
    {
        var payload = await GetFirstAsync<BiDashboardsPayload>(["/api/mobile/bi/dashboards", "/tenant/api/mobile/bi/dashboards"], cancellationToken);
        return payload?.Dashboards ?? [];
    }

    public async Task<MobileBiDashboardDetail?> GetBiDashboardDetailAsync(int dashboardId, CancellationToken cancellationToken)
    {
        if (dashboardId <= 0)
        {
            return null;
        }

        var payload = await GetFirstAsync<BiDashboardDetailPayload>(
            [
                $"/api/mobile/bi/dashboards/{dashboardId}",
                $"/tenant/api/mobile/bi/dashboards/{dashboardId}",
            ],
            cancellationToken);
        return payload?.Dashboard;
    }

    public async Task<(bool Ok, string Message, MobileBiQueryResult? Result)> ExecuteBiQueryAsync(
        string sql,
        string dataSourceToken,
        int rowLimit,
        CancellationToken cancellationToken)
    {
        var body = new
        {
            sql,
            dataSource = dataSourceToken,
            rowLimit = Math.Clamp(rowLimit, 1, 200),
        };

        foreach (var baseUrl in BackendEndpoints.Candidates())
        {
            foreach (var path in new[] { "/api/mobile/bi/query", "/tenant/api/mobile/bi/query" })
            {
                var endpoint = BuildUrl(baseUrl, path);
                try
                {
                    var response = await _httpClient.PostAsJsonAsync(endpoint, body, cancellationToken);
                    var payload = await response.Content.ReadFromJsonAsync<BiQueryPayload>(cancellationToken: cancellationToken);
                    if (response.IsSuccessStatusCode && payload is not null && payload.Ok)
                    {
                        var result = new MobileBiQueryResult
                        {
                            Columns = payload.Columns ?? [],
                            ElapsedMs = payload.ElapsedMs,
                        };

                        if (payload.Rows is not null)
                        {
                            foreach (var row in payload.Rows)
                            {
                                var mappedRow = new List<string>();
                                foreach (var cell in row)
                                {
                                    mappedRow.Add(ReadJsonCell(cell));
                                }
                                result.Rows.Add(mappedRow);
                            }
                        }

                        var message = string.IsNullOrWhiteSpace(payload.Message)
                            ? $"{result.Rows.Count} row(s) returned in {result.ElapsedMs} ms"
                            : payload.Message;
                        return (true, message, result);
                    }

                    if (payload is not null && !string.IsNullOrWhiteSpace(payload.Message))
                    {
                        return (false, payload.Message, null);
                    }
                }
                catch
                {
                    // try next endpoint candidate
                }
            }
        }

        return (false, "Query service unavailable.", null);
    }

    public async Task<IReadOnlyList<MobileKanbanColumn>> GetKanbanAsync(CancellationToken cancellationToken)
    {
        var payload = await GetFirstAsync<KanbanPayload>("/api/mobile/kanban", cancellationToken);
        return payload?.Columns ?? [];
    }

    public async Task<(bool Ok, string Message)> MoveKanbanCardAsync(string itemId, string targetColumn, CancellationToken cancellationToken)
    {
        var body = new
        {
            itemId,
            targetColumn,
        };

        foreach (var baseUrl in BackendEndpoints.Candidates())
        {
            var endpoint = BuildUrl(baseUrl, "/api/mobile/kanban/move");
            try
            {
                var response = await _httpClient.PostAsJsonAsync(endpoint, body, cancellationToken);
                var payload = await response.Content.ReadFromJsonAsync<MoveCardPayload>(cancellationToken: cancellationToken);
                if (response.IsSuccessStatusCode && payload?.Ok == true)
                {
                    return (true, payload.Message);
                }

                if (payload is not null && !string.IsNullOrWhiteSpace(payload.Message))
                {
                    return (false, payload.Message);
                }
            }
            catch
            {
                // try next endpoint
            }
        }

        return (false, "Impossible de deplacer la carte.");
    }

    public async Task<(bool Ok, string Message)> CreateKanbanTaskAsync(
        string title,
        string description,
        string owner,
        string priority,
        string dueDate,
        string column,
        CancellationToken cancellationToken)
    {
        var body = new
        {
            title,
            description,
            owner,
            priority,
            dueDate,
            column,
        };

        foreach (var baseUrl in BackendEndpoints.Candidates())
        {
            var endpoint = BuildUrl(baseUrl, "/api/mobile/kanban/tasks");
            try
            {
                var response = await _httpClient.PostAsJsonAsync(endpoint, body, cancellationToken);
                var payload = await response.Content.ReadFromJsonAsync<MoveCardPayload>(cancellationToken: cancellationToken);
                if (response.IsSuccessStatusCode && payload?.Ok == true)
                {
                    return (true, payload.Message);
                }

                if (payload is not null && !string.IsNullOrWhiteSpace(payload.Message))
                {
                    return (false, payload.Message);
                }
            }
            catch
            {
                // try next endpoint
            }
        }

        return (false, "Impossible de creer la tache.");
    }

    public async Task<(bool Ok, string Message)> UpdateKanbanTaskAsync(
        string itemId,
        string title,
        string description,
        string owner,
        string priority,
        string dueDate,
        string column,
        CancellationToken cancellationToken)
    {
        var body = new
        {
            title,
            description,
            owner,
            priority,
            dueDate,
            column,
        };

        foreach (var baseUrl in BackendEndpoints.Candidates())
        {
            var endpoint = BuildUrl(baseUrl, $"/api/mobile/kanban/tasks/{Uri.EscapeDataString(itemId)}");
            try
            {
                var response = await _httpClient.PutAsJsonAsync(endpoint, body, cancellationToken);
                var payload = await response.Content.ReadFromJsonAsync<MoveCardPayload>(cancellationToken: cancellationToken);
                if (response.IsSuccessStatusCode && payload?.Ok == true)
                {
                    return (true, payload.Message);
                }

                if (payload is not null && !string.IsNullOrWhiteSpace(payload.Message))
                {
                    return (false, payload.Message);
                }
            }
            catch
            {
                // try next endpoint
            }
        }

        return (false, "Impossible de modifier la tache.");
    }

    public async Task<IReadOnlyList<MobileLearningEnrollment>> GetLearningAsync(CancellationToken cancellationToken)
    {
        var payload = await GetFirstAsync<LearningPayload>("/api/mobile/learning", cancellationToken);
        return payload?.Enrollments ?? [];
    }

    public async Task<IReadOnlyList<MobileLearningLesson>> GetLearningContentAsync(CancellationToken cancellationToken)
    {
        var payload = await GetFirstAsync<LearningContentPayload>("/api/mobile/learning/content", cancellationToken);
        return payload?.Lessons ?? [];
    }

    public async Task<IReadOnlyList<MobileLearningQuizSummary>> GetLearningQuizzesAsync(CancellationToken cancellationToken)
    {
        var payload = await GetFirstAsync<LearningQuizzesPayload>("/api/mobile/learning/quizzes", cancellationToken);
        return payload?.Quizzes ?? [];
    }

    public async Task<(bool Ok, string Message)> SubmitLearningSubscriptionIntentAsync(string planCode, CancellationToken cancellationToken)
    {
        var body = new { planCode };

        foreach (var baseUrl in BackendEndpoints.Candidates())
        {
            var endpoint = BuildUrl(baseUrl, "/api/mobile/learning/subscription/intent");
            try
            {
                var response = await _httpClient.PostAsJsonAsync(endpoint, body, cancellationToken);
                var payload = await response.Content.ReadFromJsonAsync<MoveCardPayload>(cancellationToken: cancellationToken);
                if (response.IsSuccessStatusCode && payload?.Ok == true)
                {
                    return (true, payload.Message);
                }

                if (payload is not null && !string.IsNullOrWhiteSpace(payload.Message))
                {
                    return (false, payload.Message);
                }
            }
            catch
            {
                // try next endpoint
            }
        }

        return (false, "Impossible d'envoyer la demande d'abonnement learning.");
    }

    public async Task<(bool Ok, string Message)> SubmitLearningModuleSubscriptionAsync(int moduleId, string moduleCode, string moduleTitle, CancellationToken cancellationToken)
    {
        var body = new
        {
            moduleId,
            moduleCode,
            moduleTitle,
        };

        foreach (var baseUrl in BackendEndpoints.Candidates())
        {
            foreach (var path in new[] { "/api/mobile/learning/modules/subscribe", "/tenant/api/mobile/learning/modules/subscribe" })
            {
                var endpoint = BuildUrl(baseUrl, path);
                try
                {
                    var response = await _httpClient.PostAsJsonAsync(endpoint, body, cancellationToken);
                    var payload = await response.Content.ReadFromJsonAsync<MoveCardPayload>(cancellationToken: cancellationToken);
                    if (response.IsSuccessStatusCode && payload?.Ok == true)
                    {
                        return (true, payload.Message);
                    }

                    if (payload is not null && !string.IsNullOrWhiteSpace(payload.Message))
                    {
                        return (false, payload.Message);
                    }
                }
                catch
                {
                    // try next endpoint candidate
                }
            }
        }

        return (false, "Impossible d'envoyer la demande d'abonnement module.");
    }

    public async Task<MobileLearningModuleDetail?> GetLearningModuleDetailAsync(int moduleId, CancellationToken cancellationToken)
    {
        if (moduleId <= 0)
        {
            return null;
        }

        var payload = await GetFirstAsync<LearningModuleDetailPayload>($"/api/mobile/learning/modules/{moduleId}", cancellationToken);
        return payload?.Module;
    }

    public async Task<MobileLearningQuizDetail?> GetLearningQuizDetailAsync(int quizId, CancellationToken cancellationToken)
    {
        if (quizId <= 0)
        {
            return null;
        }

        var payload = await GetFirstAsync<LearningQuizDetailPayload>($"/api/mobile/learning/quizzes/{quizId}", cancellationToken);
        return payload?.Quiz;
    }

    public async Task<(bool Ok, string Message, MobileLearningQuizResult? Result)> SubmitLearningQuizAsync(int quizId, Dictionary<string, object> answers, CancellationToken cancellationToken)
    {
        if (quizId <= 0)
        {
            return (false, "Quiz invalide.", null);
        }

        var body = new
        {
            answers,
        };

        foreach (var baseUrl in BackendEndpoints.Candidates())
        {
            var endpoint = BuildUrl(baseUrl, $"/api/mobile/learning/quizzes/{quizId}/submit");
            try
            {
                var response = await _httpClient.PostAsJsonAsync(endpoint, body, cancellationToken);
                var payload = await response.Content.ReadFromJsonAsync<LearningQuizSubmitPayload>(cancellationToken: cancellationToken);
                if (response.IsSuccessStatusCode && payload?.Ok == true)
                {
                    return (true, payload.Message, payload.Result);
                }

                if (payload is not null && !string.IsNullOrWhiteSpace(payload.Message))
                {
                    return (false, payload.Message, payload.Result);
                }
            }
            catch
            {
                // try next endpoint
            }
        }

        return (false, "Impossible de soumettre le quiz.", null);
    }

    public async Task<(bool Ok, string Message, string Model)> AskAiAsync(string message, string dataSource, string language, CancellationToken cancellationToken)
    {
        var body = new
        {
            message,
            dataSource,
            lang = language,
        };

        foreach (var baseUrl in BackendEndpoints.Candidates())
        {
            var endpoint = BuildUrl(baseUrl, "/api/mobile/ai/chat");
            try
            {
                var response = await _httpClient.PostAsJsonAsync(endpoint, body, cancellationToken);
                var payload = await response.Content.ReadFromJsonAsync<AiChatPayload>(cancellationToken: cancellationToken);
                if (response.IsSuccessStatusCode && payload is not null && payload.Ok)
                {
                    return (true, payload.Message, payload.Model);
                }

                if (payload is not null && !string.IsNullOrWhiteSpace(payload.Message))
                {
                    return (false, payload.Message, string.Empty);
                }
            }
            catch
            {
                // try next endpoint
            }
        }

        return (false, "Assistant AI indisponible pour le moment.", string.Empty);
    }

    public async Task<(string Model, string Provider, string Label)> GetAiProfileInfoAsync(CancellationToken cancellationToken)
    {
        var payload = await GetFirstAsync<AiProfileInfoPayload>(
            ["/api/mobile/profile/ai-info", "/tenant/api/mobile/profile/ai-info"],
            cancellationToken);
        if (payload is null)
        {
            return ("gpt-4o-mini", "openai", "OPENAI · gpt-4o-mini");
        }

        return (payload.Model, payload.Provider, payload.Label);
    }

    public async Task<(bool Ok, string Message, string Provider, string Model, string Label)> UpdateAiProfileRuntimeAsync(
        string provider,
        string model,
        CancellationToken cancellationToken)
    {
        var body = new
        {
            provider = string.IsNullOrWhiteSpace(provider) ? "openai" : provider.Trim().ToLowerInvariant(),
            model = model?.Trim() ?? string.Empty,
        };

        foreach (var baseUrl in BackendEndpoints.Candidates())
        {
            foreach (var path in new[] { "/api/mobile/profile/ai-runtime", "/tenant/api/mobile/profile/ai-runtime" })
            {
                var endpoint = BuildUrl(baseUrl, path);
                try
                {
                    var response = await _httpClient.PostAsJsonAsync(endpoint, body, cancellationToken);
                    var payload = await response.Content.ReadFromJsonAsync<AiRuntimeUpdatePayload>(cancellationToken: cancellationToken);
                    if (response.IsSuccessStatusCode && payload is not null && payload.Ok)
                    {
                        return (true, payload.Message, payload.Provider, payload.Model, payload.Label);
                    }

                    if (payload is not null)
                    {
                        return (
                            false,
                            string.IsNullOrWhiteSpace(payload.Message) ? "Unable to update AI runtime." : payload.Message,
                            payload.Provider,
                            payload.Model,
                            payload.Label);
                    }
                }
                catch
                {
                    // try next endpoint candidate
                }
            }
        }

        return (false, "AI runtime update service unavailable.", string.Empty, string.Empty, string.Empty);
    }

    public async Task<IReadOnlyList<MobileFinanceEntry>> GetFinanceEntriesAsync(CancellationToken cancellationToken)
    {
        var payload = await GetFirstAsync<FinancePayload>("/api/mobile/finance/entries", cancellationToken);
        return payload?.Entries ?? [];
    }

    public async Task<IReadOnlyList<MobileFinanceAccount>> GetFinanceAccountsAsync(CancellationToken cancellationToken)
    {
        var payload = await GetFirstAsync<FinanceAccountsPayload>("/api/mobile/finance/accounts", cancellationToken);
        return payload?.Accounts ?? [];
    }

    public async Task<MobileFinanceCategoryReport> GetFinanceCategoryReportAsync(CancellationToken cancellationToken)
    {
        var payload = await GetFirstAsync<FinanceCategoryReportPayload>("/api/mobile/finance/category-report", cancellationToken);
        return payload is null
            ? new MobileFinanceCategoryReport()
            : new MobileFinanceCategoryReport
            {
                Expenses = payload.Expenses,
                Revenues = payload.Revenues,
            };
    }

    public async Task<(bool Ok, string Message)> AddFinanceEntryAsync(string description, string category, double amount, int? accountId, CancellationToken cancellationToken)
    {
        var body = new
        {
            description,
            category,
            amount,
            accountId,
        };

        foreach (var baseUrl in BackendEndpoints.Candidates())
        {
            var endpoint = BuildUrl(baseUrl, "/api/mobile/finance/entries");
            try
            {
                var response = await _httpClient.PostAsJsonAsync(endpoint, body, cancellationToken);
                var payload = await response.Content.ReadFromJsonAsync<FinanceCreatePayload>(cancellationToken: cancellationToken);
                if (response.IsSuccessStatusCode && payload?.Ok == true)
                {
                    return (true, payload.Message);
                }

                if (payload is not null && !string.IsNullOrWhiteSpace(payload.Message))
                {
                    return (false, payload.Message);
                }
            }
            catch
            {
                // try next candidate endpoint
            }
        }

        return (false, "Impossible d'ajouter la saisie finance.");
    }

    public async Task<MobileFinanceSummary> GetFinanceSummaryAsync(CancellationToken cancellationToken)
    {
        var payload = await GetFirstAsync<FinanceSummaryPayload>("/api/mobile/finance/summary", cancellationToken);
        if (payload is null)
        {
            return new MobileFinanceSummary();
        }

        return new MobileFinanceSummary
        {
            DailyIn = payload.Daily.In,
            DailyOut = payload.Daily.Out,
            DailyNet = payload.Daily.Net,
            MonthlyIn = payload.Monthly.In,
            MonthlyOut = payload.Monthly.Out,
            MonthlyNet = payload.Monthly.Net,
        };
    }

    private async Task<T?> GetFirstAsync<T>(string path, CancellationToken cancellationToken)
    {
        foreach (var baseUrl in BackendEndpoints.Candidates())
        {
            var endpoint = BuildUrl(baseUrl, path);
            try
            {
                var payload = await _httpClient.GetFromJsonAsync<T>(endpoint, cancellationToken);
                if (payload is not null)
                {
                    return payload;
                }
            }
            catch
            {
                // try next candidate endpoint
            }
        }

        return default;
    }

    private async Task<T?> GetFirstAsync<T>(IEnumerable<string> paths, CancellationToken cancellationToken)
    {
        foreach (var path in paths)
        {
            var payload = await GetFirstAsync<T>(path, cancellationToken);
            if (payload is not null)
            {
                return payload;
            }
        }

        return default;
    }

    private static string BuildUrl(string baseUrl, string path)
    {
        TenantSessionStore.LoadFromDevice();
        var tenantSlug = TenantSessionStore.Current?.TenantSlug?.Trim();
        if (!string.IsNullOrWhiteSpace(tenantSlug))
        {
            return $"{baseUrl}{path}?tenant={Uri.EscapeDataString(tenantSlug)}";
        }

        return $"{baseUrl}{path}";
    }

    private static string ReadJsonCell(JsonElement element)
    {
        return element.ValueKind switch
        {
            JsonValueKind.Null => string.Empty,
            JsonValueKind.String => element.GetString() ?? string.Empty,
            JsonValueKind.Number => element.GetRawText(),
            JsonValueKind.True => "true",
            JsonValueKind.False => "false",
            _ => element.GetRawText(),
        };
    }

    private sealed class DashboardPayload
    {
        [JsonPropertyName("dashboardCount")]
        public int DashboardCount { get; set; }

        [JsonPropertyName("queryRunCount")]
        public int QueryRunCount { get; set; }

        [JsonPropertyName("financeEntriesCount")]
        public int FinanceEntriesCount { get; set; }

        [JsonPropertyName("financeNetAmount")]
        public double FinanceNetAmount { get; set; }

        [JsonPropertyName("learningModulesCount")]
        public int LearningModulesCount { get; set; }

        [JsonPropertyName("learningProgressAvg")]
        public int LearningProgressAvg { get; set; }
    }

    private sealed class KanbanPayload
    {
        [JsonPropertyName("columns")]
        public List<MobileKanbanColumn> Columns { get; set; } = [];
    }

    private sealed class LearningPayload
    {
        [JsonPropertyName("enrollments")]
        public List<MobileLearningEnrollment> Enrollments { get; set; } = [];
    }

    private sealed class LearningContentPayload
    {
        [JsonPropertyName("lessons")]
        public List<MobileLearningLesson> Lessons { get; set; } = [];
    }

    private sealed class LearningQuizzesPayload
    {
        [JsonPropertyName("quizzes")]
        public List<MobileLearningQuizSummary> Quizzes { get; set; } = [];
    }

    private sealed class LearningModuleDetailPayload
    {
        [JsonPropertyName("ok")]
        public bool Ok { get; set; }

        [JsonPropertyName("module")]
        public MobileLearningModuleDetail? Module { get; set; }
    }

    private sealed class LearningQuizDetailPayload
    {
        [JsonPropertyName("ok")]
        public bool Ok { get; set; }

        [JsonPropertyName("quiz")]
        public MobileLearningQuizDetail? Quiz { get; set; }
    }

    private sealed class LearningQuizSubmitPayload
    {
        [JsonPropertyName("ok")]
        public bool Ok { get; set; }

        [JsonPropertyName("message")]
        public string Message { get; set; } = string.Empty;

        [JsonPropertyName("result")]
        public MobileLearningQuizResult? Result { get; set; }
    }

    private sealed class FinancePayload
    {
        [JsonPropertyName("entries")]
        public List<MobileFinanceEntry> Entries { get; set; } = [];
    }

    private sealed class FinanceAccountsPayload
    {
        [JsonPropertyName("accounts")]
        public List<MobileFinanceAccount> Accounts { get; set; } = [];
    }

    private sealed class FinanceCategoryReportPayload
    {
        [JsonPropertyName("expenses")]
        public List<MobileFinanceCategoryTotal> Expenses { get; set; } = [];

        [JsonPropertyName("revenues")]
        public List<MobileFinanceCategoryTotal> Revenues { get; set; } = [];
    }

    private sealed class BiDataSourcePayload
    {
        [JsonPropertyName("datasources")]
        public List<MobileBiDataSource> Datasources { get; set; } = [];
    }

    private sealed class BiDashboardsPayload
    {
        [JsonPropertyName("dashboards")]
        public List<MobileBiDashboardSummary> Dashboards { get; set; } = [];
    }

    private sealed class BiDashboardDetailPayload
    {
        [JsonPropertyName("ok")]
        public bool Ok { get; set; }

        [JsonPropertyName("dashboard")]
        public MobileBiDashboardDetail? Dashboard { get; set; }
    }

    private sealed class BiQueryPayload
    {
        [JsonPropertyName("ok")]
        public bool Ok { get; set; }

        [JsonPropertyName("message")]
        public string Message { get; set; } = string.Empty;

        [JsonPropertyName("columns")]
        public List<string>? Columns { get; set; }

        [JsonPropertyName("rows")]
        public List<List<JsonElement>>? Rows { get; set; }

        [JsonPropertyName("elapsedMs")]
        public int ElapsedMs { get; set; }
    }

    private sealed class FinanceCreatePayload
    {
        [JsonPropertyName("ok")]
        public bool Ok { get; set; }

        [JsonPropertyName("message")]
        public string Message { get; set; } = string.Empty;
    }

    private sealed class MoveCardPayload
    {
        [JsonPropertyName("ok")]
        public bool Ok { get; set; }

        [JsonPropertyName("message")]
        public string Message { get; set; } = string.Empty;
    }

    private sealed class AiChatPayload
    {
        [JsonPropertyName("ok")]
        public bool Ok { get; set; }

        [JsonPropertyName("message")]
        public string Message { get; set; } = string.Empty;

        [JsonPropertyName("model")]
        public string Model { get; set; } = string.Empty;

        [JsonPropertyName("provider")]
        public string Provider { get; set; } = string.Empty;
    }

    private sealed class AiProfileInfoPayload
    {
        [JsonPropertyName("ok")]
        public bool Ok { get; set; }

        [JsonPropertyName("model")]
        public string Model { get; set; } = "gpt-4o-mini";

        [JsonPropertyName("provider")]
        public string Provider { get; set; } = "openai";

        [JsonPropertyName("label")]
        public string Label { get; set; } = "OPENAI · gpt-4o-mini";
    }

    private sealed class AiRuntimeUpdatePayload
    {
        [JsonPropertyName("ok")]
        public bool Ok { get; set; }

        [JsonPropertyName("message")]
        public string Message { get; set; } = string.Empty;

        [JsonPropertyName("provider")]
        public string Provider { get; set; } = string.Empty;

        [JsonPropertyName("model")]
        public string Model { get; set; } = string.Empty;

        [JsonPropertyName("label")]
        public string Label { get; set; } = string.Empty;
    }

    private sealed class FinanceSummaryPayload
    {
        [JsonPropertyName("daily")]
        public FinancePeriod Daily { get; set; } = new();

        [JsonPropertyName("monthly")]
        public FinancePeriod Monthly { get; set; } = new();
    }

    private sealed class FinancePeriod
    {
        [JsonPropertyName("in")]
        public double In { get; set; }

        [JsonPropertyName("out")]
        public double Out { get; set; }

        [JsonPropertyName("net")]
        public double Net { get; set; }
    }
}
