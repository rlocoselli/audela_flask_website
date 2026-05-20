using Microsoft.Extensions.Logging;
using AudelaMobileLight.Services;
#if ANDROID
using AudelaMobileLight.Platforms.Android;
#endif

namespace AudelaMobileLight;

public static class MauiProgram
{
	public static MauiApp CreateMauiApp()
	{
		var builder = MauiApp.CreateBuilder();
		builder
			.UseMauiApp<App>()
			.ConfigureFonts(fonts =>
			{
				fonts.AddFont("OpenSans-Regular.ttf", "OpenSansRegular");
				fonts.AddFont("OpenSans-Semibold.ttf", "OpenSansSemibold");
			});

#if DEBUG
		builder.Logging.AddDebug();
#endif

#if ANDROID
		builder.Services.AddSingleton<IVoiceRecognitionService, AndroidVoiceRecognitionService>();
#else
		builder.Services.AddSingleton<IVoiceRecognitionService, NoopVoiceRecognitionService>();
#endif

		return builder.Build();
	}
}
