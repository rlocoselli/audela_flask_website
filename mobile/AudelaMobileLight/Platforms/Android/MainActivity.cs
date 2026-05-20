using Android.App;
using Android.Content;
using Android.Content.PM;
using Android.OS;

namespace AudelaMobileLight;

[Activity(Theme = "@style/Maui.SplashTheme", MainLauncher = true, LaunchMode = LaunchMode.SingleTop, ConfigurationChanges = ConfigChanges.ScreenSize | ConfigChanges.Orientation | ConfigChanges.UiMode | ConfigChanges.ScreenLayout | ConfigChanges.SmallestScreenSize | ConfigChanges.Density)]
[IntentFilter(
	[Intent.ActionView],
	Categories = [Intent.CategoryDefault, Intent.CategoryBrowsable],
	DataScheme = "audelamobilelight",
	DataHost = "oauth-callback")]
public class MainActivity : MauiAppCompatActivity
{
	protected override void OnCreate(Bundle? savedInstanceState)
	{
		base.OnCreate(savedInstanceState);
		ForwardDeepLink(Intent);
	}

	protected override void OnNewIntent(Intent? intent)
	{
		base.OnNewIntent(intent);
		ForwardDeepLink(intent);
	}

	private static void ForwardDeepLink(Intent? intent)
	{
		var uri = intent?.DataString;
		if (string.IsNullOrWhiteSpace(uri))
		{
			return;
		}

		App.HandleDeepLink(uri);
	}
}
