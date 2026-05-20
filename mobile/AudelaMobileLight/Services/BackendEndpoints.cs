namespace AudelaMobileLight.Services;

public static class BackendEndpoints
{
    private static readonly string[] PublicBaseUrls =
    [
        "https://audeladedonnees.fr",
        "https://grenobleski.fr",
        "https://www.audeladedonnees.fr",
        "https://www.grenobleski.fr",
    ];

#if DEBUG
    private static readonly string[] LocalBaseUrls =
    [
        "http://10.0.2.2:5000",
        "http://127.0.0.1:5000",
        "http://localhost:5000",
    ];
#endif

    public static string PrimaryPublicBaseUrl => PublicBaseUrls[0];

    public static IReadOnlyList<string> Candidates()
    {
        var urls = new List<string>(PublicBaseUrls.Length + 3);
        urls.AddRange(PublicBaseUrls);
#if DEBUG
        urls.AddRange(LocalBaseUrls);
#endif
        return urls;
    }
}