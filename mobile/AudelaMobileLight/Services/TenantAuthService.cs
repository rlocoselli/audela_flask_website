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

    private readonly string[] _baseUrls =
    [
        "http://10.0.2.2:5000",
        "http://127.0.0.1:5000",
        "https://audeladedonnees.fr",
    ];

    public async Task<(bool Ok, string Message, TenantSession? Session)> LoginAsync(string tenantSlug, string email, string password)
    {
        var payload = new
        {
            tenantSlug,
            email,
            password,
        };

        foreach (var baseUrl in _baseUrls)
        {
            try
            {
                var response = await _httpClient.PostAsJsonAsync($"{baseUrl}/tenant/api/mobile/login", payload);
                var result = await response.Content.ReadFromJsonAsync<LoginResponse>();
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

                return (false, result?.Message ?? "Login failed.", null);
            }
            catch
            {
                // Try next base URL.
            }
        }

        return (false, "Server unavailable. Check API URL or backend status.", null);
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

        foreach (var baseUrl in _baseUrls)
        {
            try
            {
                var response = await _httpClient.PostAsJsonAsync($"{baseUrl}/tenant/api/mobile/register", payload);
                var result = await response.Content.ReadFromJsonAsync<BaseResponse>();
                if (response.IsSuccessStatusCode && result?.Ok == true)
                {
                    return (true, result.Message);
                }

                return (false, result?.Message ?? "Registration failed.");
            }
            catch
            {
                // Try next base URL.
            }
        }

        return (false, "Server unavailable. Check API URL or backend status.");
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
