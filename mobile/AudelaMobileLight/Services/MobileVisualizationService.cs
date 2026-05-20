using System.Net.Http.Json;
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
                KanbanBacklog = payload.Kanban.Backlog,
                KanbanTodo = payload.Kanban.Todo,
                KanbanDoing = payload.Kanban.Doing,
                KanbanDone = payload.Kanban.Done,
            };
    }

    public async Task<IReadOnlyList<MobileKanbanColumn>> GetKanbanAsync(CancellationToken cancellationToken)
    {
        var payload = await GetFirstAsync<KanbanPayload>("/api/mobile/kanban", cancellationToken);
        return payload?.Columns ?? [];
    }

    public async Task<IReadOnlyList<MobileLearningEnrollment>> GetLearningAsync(CancellationToken cancellationToken)
    {
        var payload = await GetFirstAsync<LearningPayload>("/api/mobile/learning", cancellationToken);
        return payload?.Enrollments ?? [];
    }

    public async Task<IReadOnlyList<MobileFinanceEntry>> GetFinanceEntriesAsync(CancellationToken cancellationToken)
    {
        var payload = await GetFirstAsync<FinancePayload>("/api/mobile/finance/entries", cancellationToken);
        return payload?.Entries ?? [];
    }

    public async Task<(bool Ok, string Message)> AddFinanceEntryAsync(string description, string category, double amount, CancellationToken cancellationToken)
    {
        var body = new
        {
            description,
            category,
            amount,
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

        [JsonPropertyName("kanban")]
        public KanbanCounts Kanban { get; set; } = new();
    }

    private sealed class KanbanCounts
    {
        [JsonPropertyName("backlog")]
        public int Backlog { get; set; }

        [JsonPropertyName("todo")]
        public int Todo { get; set; }

        [JsonPropertyName("doing")]
        public int Doing { get; set; }

        [JsonPropertyName("done")]
        public int Done { get; set; }
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

    private sealed class FinancePayload
    {
        [JsonPropertyName("entries")]
        public List<MobileFinanceEntry> Entries { get; set; } = [];
    }

    private sealed class FinanceCreatePayload
    {
        [JsonPropertyName("ok")]
        public bool Ok { get; set; }

        [JsonPropertyName("message")]
        public string Message { get; set; } = string.Empty;
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
