namespace AudelaMobileLight.Services;

public sealed class NoopVoiceRecognitionService : IVoiceRecognitionService
{
    public Task<(bool Ok, string Text, string Message)> RecognizeAsync(CancellationToken cancellationToken)
    {
        return Task.FromResult((false, string.Empty, MobileLocalizer.T("finance.voiceUnavailable")));
    }
}
