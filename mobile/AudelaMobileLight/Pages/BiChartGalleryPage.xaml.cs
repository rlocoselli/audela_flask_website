using System.Collections.ObjectModel;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;
using Microsoft.Maui.Controls.Shapes;

namespace AudelaMobileLight.Pages;

public class BiChartGalleryPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    private readonly Picker _dashboardPicker;

    public ObservableCollection<MobileBiDashboardSummary> Dashboards { get; } = [];
    public ObservableCollection<MobileBiDashboardCard> Cards { get; } = [];

    public MobileBiDashboardSummary? SelectedDashboard { get; set; }
    public bool IsLoading { get; private set; }

    public BiChartGalleryPage()
    {
        Title = "BI Chart Gallery";

        _dashboardPicker = new Picker
        {
            Title = "Select dashboard",
            ItemDisplayBinding = new Binding(nameof(MobileBiDashboardSummary.Name)),
            TextColor = Colors.White,
            TitleColor = Color.FromArgb("#C7DAFF"),
        };
        _dashboardPicker.SetBinding(Picker.ItemsSourceProperty, nameof(Dashboards));
        _dashboardPicker.SetBinding(Picker.SelectedItemProperty, nameof(SelectedDashboard));
        _dashboardPicker.SelectedIndexChanged += OnDashboardChanged;

        var cardsView = new CollectionView
        {
            HeightRequest = 560,
        };
        cardsView.SetBinding(ItemsView.ItemsSourceProperty, nameof(Cards));
        cardsView.ItemTemplate = new DataTemplate(() =>
        {
            var title = new Label { FontAttributes = FontAttributes.Bold, TextColor = Color.FromArgb("#163252") };
            title.SetBinding(Label.TextProperty, nameof(MobileBiDashboardCard.Title));

            var type = new Label { FontSize = 11, TextColor = Color.FromArgb("#5E7392") };
            type.SetBinding(Label.TextProperty, nameof(MobileBiDashboardCard.VizTypeNormalized));

            var source = new Label { FontSize = 12, TextColor = Color.FromArgb("#4C6588") };
            source.SetBinding(Label.TextProperty, nameof(MobileBiDashboardCard.SourceName));

            var primary = new Label { FontAttributes = FontAttributes.Bold, TextColor = Color.FromArgb("#0A2F8A") };
            primary.SetBinding(Label.TextProperty, nameof(MobileBiDashboardCard.PrimaryValue));

            var trend = new Label { FontSize = 10, TextColor = Color.FromArgb("#6A7FA0"), MaxLines = 2, LineBreakMode = LineBreakMode.TailTruncation };
            trend.SetBinding(Label.TextProperty, nameof(MobileBiDashboardCard.TrendLabel));

            var grid = new Grid
            {
                ColumnDefinitions = new ColumnDefinitionCollection
                {
                    new ColumnDefinition(GridLength.Star),
                    new ColumnDefinition(GridLength.Auto),
                },
                ColumnSpacing = 8,
                Children = { title, type },
            };
            Grid.SetColumn(type, 1);

            return new Border
            {
                Stroke = Color.FromArgb("#DDE7F5"),
                StrokeThickness = 1,
                BackgroundColor = Colors.White,
                Padding = 10,
                Margin = new Thickness(0, 0, 0, 8),
                StrokeShape = new RoundRectangle { CornerRadius = new CornerRadius(12) },
                Content = new VerticalStackLayout
                {
                    Spacing = 6,
                    Children =
                    {
                        grid,
                        source,
                        new Border
                        {
                            StrokeThickness = 0,
                            BackgroundColor = Color.FromArgb("#EEF4FF"),
                            Padding = new Thickness(8, 4),
                            StrokeShape = new RoundRectangle { CornerRadius = new CornerRadius(8) },
                            Content = primary,
                        },
                        trend,
                    },
                },
            };
        });

        var loading = new ActivityIndicator();
        loading.SetBinding(ActivityIndicator.IsVisibleProperty, nameof(IsLoading));
        loading.SetBinding(ActivityIndicator.IsRunningProperty, nameof(IsLoading));

        Content = new ScrollView
        {
            BackgroundColor = Color.FromArgb("#EEF3FB"),
            Content = new VerticalStackLayout
            {
                Padding = 14,
                Spacing = 12,
                Children =
                {
                    new Border
                    {
                        StrokeThickness = 0,
                        Padding = 14,
                        StrokeShape = new RoundRectangle { CornerRadius = new CornerRadius(20) },
                        Background = new LinearGradientBrush(
                            new GradientStopCollection
                            {
                                new GradientStop(Color.FromArgb("#0A255B"), 0.0f),
                                new GradientStop(Color.FromArgb("#1E4FBB"), 1.0f),
                            },
                            new Point(0, 0),
                            new Point(1, 1)),
                        Content = new VerticalStackLayout
                        {
                            Spacing = 8,
                            Children =
                            {
                                new Label { Text = "Chart Gallery", FontSize = 22, FontAttributes = FontAttributes.Bold, TextColor = Colors.White },
                                new Label { Text = "Bar, line, pie, KPI and table cards from your BI dashboards.", FontSize = 12, TextColor = Color.FromArgb("#C7DAFF") },
                                _dashboardPicker,
                            },
                        },
                    },
                    cardsView,
                    loading,
                },
            },
        };

        BindingContext = this;
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        await EnsureDashboardsLoadedAsync();
    }

    private async Task EnsureDashboardsLoadedAsync()
    {
        if (Dashboards.Count > 0)
        {
            return;
        }

        var dashboards = await _service.GetBiDashboardsAsync(CancellationToken.None);
        Dashboards.Clear();
        foreach (var dashboard in dashboards)
        {
            Dashboards.Add(dashboard);
        }

        SelectedDashboard = Dashboards.FirstOrDefault();
        OnPropertyChanged(nameof(SelectedDashboard));

        if (SelectedDashboard is not null)
        {
            await LoadCardsAsync(SelectedDashboard);
        }
    }

    private async void OnDashboardChanged(object? sender, EventArgs e)
    {
        if (_dashboardPicker.SelectedItem is MobileBiDashboardSummary dashboard)
        {
            SelectedDashboard = dashboard;
            OnPropertyChanged(nameof(SelectedDashboard));
            await LoadCardsAsync(dashboard);
        }
    }

    private async Task LoadCardsAsync(MobileBiDashboardSummary dashboard)
    {
        try
        {
            IsLoading = true;
            OnPropertyChanged(nameof(IsLoading));

            var detail = await _service.GetBiDashboardDetailAsync(dashboard.Id, CancellationToken.None);
            Cards.Clear();

            if (detail is null)
            {
                return;
            }

            foreach (var card in detail.Cards)
            {
                Cards.Add(card);
            }
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(IsLoading));
        }
    }
}
