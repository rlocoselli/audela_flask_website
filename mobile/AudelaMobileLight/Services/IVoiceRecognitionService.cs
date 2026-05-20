namespace AudelaMobileLight.Services;

public interface IVoiceRecognitionService
{
    Task<(bool Ok, string Text, string Message)> RecognizeAsync(CancellationToken cancellationToken);
}
