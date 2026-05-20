using AudelaMobileLight.Models;
using AudelaMobileLight.Pages;
using AudelaMobileLight.Services;

namespace AudelaMobileLight;

public partial class App : Application
{
	public App()
	{
		InitializeComponent();
	}

	protected override Window CreateWindow(IActivationState? activationState)
	{
		return new Window(new AppShell());
	}

	public static void HandleDeepLink(string uri)
	{
		if (Current is not App app)
		{
			return;
		}

		_ = MainThread.InvokeOnMainThreadAsync(() => app.ProcessDeepLinkAsync(uri));
	}

	private async Task ProcessDeepLinkAsync(string uriText)
	{
		if (!Uri.TryCreate(uriText, UriKind.Absolute, out var uri))
		{
			return;
		}

		if (!string.Equals(uri.Scheme, "audelamobilelight", StringComparison.OrdinalIgnoreCase))
		{
			return;
		}

		var query = ParseQuery(uri.Query);
		var status = GetQueryValue(query, "status");
		var message = GetQueryValue(query, "message");
		var rootPage = GetRootPage();

		if (!string.Equals(status, "success", StringComparison.OrdinalIgnoreCase))
		{
			if (!string.IsNullOrWhiteSpace(message) && rootPage is not null)
			{
				await ModernAlertService.ShowAsync(rootPage, "Google Login", message, AlertTone.Error);
			}
			return;
		}

		var tenantId = ParseInt(GetQueryValue(query, "tenantId"));
		var userId = ParseInt(GetQueryValue(query, "userId"));
		if (tenantId <= 0 || userId <= 0)
		{
			return;
		}

		TenantSessionStore.Save(new TenantSession
		{
			TenantId = tenantId,
			TenantName = GetQueryValue(query, "tenantName") ?? string.Empty,
			TenantSlug = GetQueryValue(query, "tenantSlug") ?? string.Empty,
			UserId = userId,
			UserEmail = GetQueryValue(query, "email") ?? string.Empty,
			FullName = GetQueryValue(query, "fullName") ?? string.Empty,
		});

		if (rootPage is AppShell shell)
		{
			await shell.Navigation.PushAsync(new TenantAccountPage());
		}

		if (!string.IsNullOrWhiteSpace(message) && rootPage is not null)
		{
			await ModernAlertService.ShowAsync(rootPage, "Google Login", message, AlertTone.Success);
		}
	}

	private static Dictionary<string, string> ParseQuery(string query)
	{
		var map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
		if (string.IsNullOrWhiteSpace(query))
		{
			return map;
		}

		var text = query.TrimStart('?');
		var pairs = text.Split('&', StringSplitOptions.RemoveEmptyEntries);
		foreach (var pair in pairs)
		{
			var kv = pair.Split('=', 2);
			if (kv.Length == 0 || string.IsNullOrWhiteSpace(kv[0]))
			{
				continue;
			}

			var key = Uri.UnescapeDataString(kv[0]);
			var value = kv.Length > 1 ? Uri.UnescapeDataString(kv[1]) : string.Empty;
			map[key] = value;
		}

		return map;
	}

	private static string? GetQueryValue(Dictionary<string, string> query, string key)
	{
		return query.TryGetValue(key, out var value) ? value : null;
	}

	private static int ParseInt(string? value)
	{
		return int.TryParse(value, out var n) ? n : 0;
	}

	private Page? GetRootPage()
	{
		if (Windows.Count == 0)
		{
			return null;
		}

		return Windows[0].Page;
	}
}