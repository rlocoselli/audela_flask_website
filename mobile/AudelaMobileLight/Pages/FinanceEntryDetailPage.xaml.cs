using AudelaMobileLight.Models;
using Microsoft.Maui.Controls.Shapes;

namespace AudelaMobileLight.Pages;

public class FinanceEntryDetailPage : ContentPage
{
    public FinanceEntryDetailPage(MobileFinanceEntry entry)
    {
        Title = "Transaction";
        BackgroundColor = Color.FromArgb("#EEF3FB");

        var isPositive = entry.Amount >= 0;
        var amountColor = isPositive ? Color.FromArgb("#1B6E3E") : Color.FromArgb("#9F2C2C");
        var amountBg = isPositive ? Color.FromArgb("#EAFAF2") : Color.FromArgb("#FFF0F0");
        var amountEmoji = isPositive ? "📈" : "📉";

        Content = new ScrollView
        {
            Content = new VerticalStackLayout
            {
                Padding = 16,
                Spacing = 14,
                Children =
                {
                    // Gradient header card
                    new Border
                    {
                        StrokeThickness = 0,
                        Padding = new Thickness(18, 20),
                        StrokeShape = new RoundRectangle { CornerRadius = new CornerRadius(22) },
                        Background = new LinearGradientBrush(
                            new GradientStopCollection
                            {
                                new GradientStop(Color.FromArgb("#0B2E54"), 0.0f),
                                new GradientStop(Color.FromArgb("#14697F"), 1.0f),
                            },
                            new Point(0, 0),
                            new Point(1, 1)),
                        Content = new VerticalStackLayout
                        {
                            Spacing = 10,
                            Children =
                            {
                                new Label
                                {
                                    Text = entry.Description,
                                    FontSize = 20,
                                    FontAttributes = FontAttributes.Bold,
                                    TextColor = Colors.White,
                                    LineBreakMode = LineBreakMode.WordWrap,
                                },
                                new Border
                                {
                                    StrokeThickness = 0,
                                    BackgroundColor = amountBg,
                                    Padding = new Thickness(14, 8),
                                    StrokeShape = new RoundRectangle { CornerRadius = new CornerRadius(12) },
                                    HorizontalOptions = LayoutOptions.Start,
                                    Content = new HorizontalStackLayout
                                    {
                                        Spacing = 8,
                                        Children =
                                        {
                                            new Label { Text = amountEmoji, FontSize = 18 },
                                            new Label
                                            {
                                                Text = entry.AmountLabel,
                                                FontSize = 24,
                                                FontAttributes = FontAttributes.Bold,
                                                TextColor = amountColor,
                                                VerticalOptions = LayoutOptions.Center,
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },

                    // Detail card
                    new Border
                    {
                        Stroke = Color.FromArgb("#D8E5F3"),
                        StrokeThickness = 1,
                        BackgroundColor = Colors.White,
                        Padding = 18,
                        StrokeShape = new RoundRectangle { CornerRadius = new CornerRadius(18) },
                        Content = new VerticalStackLayout
                        {
                            Spacing = 16,
                            Children =
                            {
                                new Label { Text = "Details", FontSize = 16, FontAttributes = FontAttributes.Bold, TextColor = Color.FromArgb("#17314A") },
                                DetailRow("📅", "Date", entry.Date),
                                new BoxView { Color = Color.FromArgb("#EEF3FB"), HeightRequest = 1 },
                                DetailRow("🏷", "Category", entry.Category.Length > 0 ? entry.Category : "—"),
                                new BoxView { Color = Color.FromArgb("#EEF3FB"), HeightRequest = 1 },
                                DetailRow("🏦", "Account", entry.Account.Length > 0 ? entry.Account : "—"),
                                new BoxView { Color = Color.FromArgb("#EEF3FB"), HeightRequest = 1 },
                                DetailRow("💶", "Amount", entry.AmountLabel),
                                new BoxView { Color = Color.FromArgb("#EEF3FB"), HeightRequest = 1 },
                                DetailRow("🔢", "ID", $"#{entry.Id}"),
                            },
                        },
                    },
                },
            },
        };
    }

    private static View DetailRow(string emoji, string label, string value)
    {
        var labelView = new Label
        {
            Text = $"{emoji}  {label}",
            FontSize = 14,
            TextColor = Color.FromArgb("#4C6D8E"),
            VerticalOptions = LayoutOptions.Center,
        };

        var valueView = new Label
        {
            Text = value,
            FontSize = 14,
            TextColor = Color.FromArgb("#12304B"),
            FontAttributes = FontAttributes.Bold,
            HorizontalOptions = LayoutOptions.End,
            VerticalOptions = LayoutOptions.Center,
            HorizontalTextAlignment = TextAlignment.End,
        };

        Grid.SetColumn(valueView, 1);

        return new Grid
        {
            ColumnDefinitions = new ColumnDefinitionCollection
            {
                new ColumnDefinition(GridLength.Star),
                new ColumnDefinition(GridLength.Star),
            },
            Children = { labelView, valueView },
        };
    }
}
