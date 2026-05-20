using System.Net.Http.Json;
using System.Text.Json.Serialization;
using AudelaMobileLight.Models;

namespace AudelaMobileLight.Services;

public sealed class TenantAuthService
{
    private readonly HttpClient _httpClient = new()
    {
        Timeout = TimeSpan.FromSeconds(8),
    };

    private readonly IReadOnlyList<string> _baseUrls = BackendEndpoints.Candidates();

    private readonly string[] _mobileLoginPaths =
    [
        "/tenant/api/mobile/login",
    ];

    private readonly string[] _mobileRegisterPaths =
    [
        "/tenant/api/mobile/register",
    ];

    public async Task<(bool Ok, string Message, TenantSession? Session)> LoginAsync(string tenantSlug, string email, string password)
    {
        var payload = new
        {
            tenantSlug,
            email,
            password,
        };

        string lastMessage = "Service indisponible. Impossible de joindre le backend AUDELA.";
        var diagnostics = new List<string>();

        foreach (var baseUrl in _baseUrls)
        {
            foreach (var path in _mobileLoginPaths)
            {
                try
                {
                    var endpoint = $"{baseUrl}{path}";
                    var response = await _httpClient.PostAsJsonAsync(endpoint, payload);
                    LoginResponse? result = null;
                    try
                    {
                        result = await response.Content.ReadFromJsonAsync<LoginResponse>();
                    }
                    catch (Exception ex)
                    {
                        diagnostics.Add($"{endpoint} -> {(int)response.StatusCode} ({ex.GetType().Name})");
                    }

                    if (response.IsSuccessStatusCode && result?.Ok == true && result.Tenant is not null && result.User is not null)
                    {
                        var fullName = ($"{result.User.FirstName} {result.User.LastName}").Trim();
                        return (true, result.Message, new TenantSession
                        {
                            TenantId = result.Tenant.Id,
                            TenantName = result.Tenant.Name,
                            TenantSlug = result.Tenant.Slug,
                            UserId = result.User.Id,
                            UserEmail = result.User.Email,
                            FullName = fullName,
                        });
                    }

                    if (result is not null && !string.IsNullOrWhiteSpace(result.Message))
                    {
                        lastMessage = result.Message;
                        if (!response.IsSuccessStatusCode)
                        {
                            diagnostics.Add($"{endpoint} -> {(int)response.StatusCode}");
                        }
                    }
                    else if (!response.IsSuccessStatusCode)
                    {
                        diagnostics.Add($"{endpoint} -> {(int)response.StatusCode}");
                    }
                }
                catch (TaskCanceledException)
                {
                    diagnostics.Add($"{baseUrl}{path} -> timeout");
                }
                catch
                {
                    diagnostics.Add($"{baseUrl}{path} -> request_failed");
                }
            }
        }

        if (diagnostics.Count > 0)
        {
            lastMessage = $"{lastMessage} Details: {string.Join(" | ", diagnostics.Take(3))}";
        }

        return (false, lastMessage, null);
    }

    public async Task<(bool Ok, string Message)> RegisterAsync(string tenantName, string email, string password, string passwordConfirm)
    {
        var payload = new
        {
            tenantName,
            email,
            password,
            passwordConfirm,
        };

        string lastMessage = "Service indisponible. Impossible de joindre le backend AUDELA.";
        var diagnostics = new List<string>();

        foreach (var baseUrl in _baseUrls)
        {
            foreach (var path in _mobileRegisterPaths)
            {
                try
                {
                    var endpoint = $"{baseUrl}{path}";
                    var response = await _httpClient.PostAsJsonAsync(endpoint, payload);
                    BaseResponse? result = null;
                    try
                    {
                        result = await response.Content.ReadFromJsonAsync<BaseResponse>();
                    }
                    catch (Exception ex)
                    {
                        diagnostics.Add($"{endpoint} -> {(int)response.StatusCode} ({ex.GetType().Name})");
                    }

                    if (response.IsSuccessStatusCode && result?.Ok == true)
                    {
                        return (true, result.Message);
                    }

                    if (result is not null && !string.IsNullOrWhiteSpace(result.Message))
                    {
                        lastMessage = result.Message;
                        if (!response.IsSuccessStatusCode)
                        {
                            diagnostics.Add($"{endpoint} -> {(int)response.StatusCode}");
                        }
                    }
                    else if (!response.IsSuccessStatusCode)
                    {
                        diagnostics.Add($"{endpoint} -> {(int)response.StatusCode}");
                    }
                }
                catch (TaskCanceledException)
                {
                    diagnostics.Add($"{baseUrl}{path} -> timeout");
                }
                catch
                {
                    diagnostics.Add($"{baseUrl}{path} -> request_failed");
                }
            }
        }

        if (diagnostics.Count > 0)
        {
            lastMessage = $"{lastMessage} Details: {string.Join(" | ", diagnostics.Take(3))}";
        }

        return (false, lastMessage);
    }

    private class BaseResponse
    {
        [JsonPropertyName("ok")]
        public bool Ok { get; set; }

        [JsonPropertyName("message")]
        public string Message { get; set; } = string.Empty;
    }

    private sealed class LoginResponse : BaseResponse
    {
        [JsonPropertyName("tenant")]
        public TenantDto? Tenant { get; set; }

        [JsonPropertyName("user")]
        public UserDto? User { get; set; }
    }

    private sealed class TenantDto
    {
        [JsonPropertyName("id")]
        public int Id { get; set; }

        [JsonPropertyName("name")]
        public string Name { get; set; } = string.Empty;

        [JsonPropertyName("slug")]
        public string Slug { get; set; } = string.Empty;
    }

    private sealed class UserDto
    {
        [JsonPropertyName("id")]
        public int Id { get; set; }

        [JsonPropertyName("email")]
        public string Email { get; set; } = string.Empty;

        [JsonPropertyName("firstName")]
        public string FirstName { get; set; } = string.Empty;

        [JsonPropertyName("lastName")]
        public string LastName { get; set; } = string.Empty;
    }
}
