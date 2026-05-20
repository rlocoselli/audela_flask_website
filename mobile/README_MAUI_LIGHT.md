# AUDELA Mobile Light (MAUI .NET)

Lightweight Android MAUI app for browsing all AUDELA products with a reduced, mobile-first feature set.

## Scope

This mobile version is intentionally simpler than the web app:

- Product catalog list (all AUDELA products)
- Product detail page (summary, audience, highlights, outcomes)
- Pull-to-refresh
- API-first data loading with offline fallback seed data

## Backend Endpoint

The Flask app now exposes:

- `GET /api/mobile/products`

The MAUI app consumes this endpoint and falls back to local seeded data if unreachable.

## Project Path

- `mobile/AudelaMobileLight`

## Run (Android)

1. Start backend:

```bash
python app2.py
```

2. Run MAUI app from project directory:

```bash
cd mobile/AudelaMobileLight
dotnet build -f net9.0-android
dotnet run -f net9.0-android
```

## API Base URLs Tried by App

In order:

1. `http://10.0.2.2:5000` (Android emulator to host machine)
2. `http://127.0.0.1:5000`
3. `https://audeladedonnees.fr`

## Main Files

- `audela/blueprints/public/routes.py` (mobile API endpoint)
- `mobile/AudelaMobileLight/MainPage.xaml` (catalog UI)
- `mobile/AudelaMobileLight/MainPage.xaml.cs` (load + navigation)
- `mobile/AudelaMobileLight/Pages/ProductDetailPage.xaml` (detail UI)
- `mobile/AudelaMobileLight/Services/ProductCatalogService.cs` (API + fallback)
- `mobile/AudelaMobileLight/Models/AudelaProduct.cs` (mobile model)
