using System.Collections.ObjectModel;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;
using Microsoft.Maui.Controls.Shapes;

namespace AudelaMobileLight.Pages;

public class BiDashboardsPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();

    public ObservableCollection<MobileBiDashboardSummary> Dashboards { get; } = [];
    public bool IsLoading { get; private set; }

    public BiDashboardsPage()
    {
        Title = "Dashboards BI";

        var list = new CollectionView
        {
            HeightRequest = 620,
        };
        list.SetBinding(ItemsView.ItemsSourceProperty, nameof(Dashboards));
        list.ItemTemplate = new DataTemplate(() =>
        {
            var title = new Label { FontAttributes = FontAttributes.Bold, TextColor = Color.FromArgb("#17314A") };
            title.SetBinding(Label.TextProperty, nameof(MobileBiDashboardSummary.Name));

            var count = new Label { FontSize = 11, TextColor = Color.FromArgb("#567295") };
            count.SetBinding(Label.TextProperty, new Binding(nameof(MobileBiDashboardSummary.CardsCount), stringFormat: "{0} cards"));

            var meta = new Label { FontSize = 12, TextColor = Color.FromArgb("#4A678A") };
            meta.SetBinding(Label.TextProperty, nameof(MobileBiDashboardSummary.MetaLabel));

            var open = new Button
            {
                Text = "Open",
                CornerRadius = 10,
                Padding = new Thickness(8, 4),
                FontSize = 11,
                MinimumHeightRequest = 30,
                MinimumWidthRequest = 30,
            };
            open.SetBinding(Button.CommandParameterProperty, ".");
            open.Clicked += OnOpenDashboardClicked;

            var row = new Grid
            {
                ColumnDefinitions = new ColumnDefinitionCollection
                {
                    new ColumnDefinition(GridLength.Star),
                    new ColumnDefinition(GridLength.Auto),
                },
                RowDefinitions = new RowDefinitionCollection
                {
                    new RowDefinition(GridLength.Auto),
                    new RowDefinition(GridLength.Auto),
                },
                ColumnSpacing = 8,
                RowSpacing = 6,
                Children = { title, count, meta, open },
            };
            Grid.SetColumn(count, 1);
            Grid.SetRow(meta, 1);
            Grid.SetRow(open, 1);
            Grid.SetColumn(open, 1);

            return new Border
            {
                Stroke = Color.FromArgb("#D8E5F3"),
                StrokeThickness = 1,
                BackgroundColor = Colors.White,
                Padding = 12,
                Margin = new Thickness(0, 0, 0, 8),
                StrokeShape = new RoundRectangle { CornerRadius = new CornerRadius(14) },
                Content = row,
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
                                new GradientStop(Color.FromArgb("#1B4BB8"), 1.0f),
                            },
                            new Point(0, 0),
                            new Point(1, 1)),
                        Content = new VerticalStackLayout
                        {
                            Spacing = 4,
                            Children =
                            {
                                new Label { Text = "BI Dashboards", FontAttributes = FontAttributes.Bold, FontSize = 24, TextColor = Colors.White },
                                new Label { Text = "Open executive dashboards with card-level details.", FontSize = 12, TextColor = Color.FromArgb("#D7E4FF") },
                            },
                        },
                    },
                    list,
                    loading,
                },
            },
        };

        BindingContext = this;
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        await LoadDashboardsAsync();
    }

    private async Task LoadDashboardsAsync()
    {
        try
        {
            IsLoading = true;
            OnPropertyChanged(nameof(IsLoading));

            var dashboards = await _service.GetBiDashboardsAsync(CancellationToken.None);
            Dashboards.Clear();
            foreach (var dashboard in dashboards)
            {
                Dashboards.Add(dashboard);
            }
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(IsLoading));
        }
    }

    private async void OnOpenDashboardClicked(object? sender, EventArgs e)
    {
        if (sender is not Button button || button.CommandParameter is not MobileBiDashboardSummary dashboard)
        {
            return;
        }

        await Navigation.PushAsync(new BiDashboardDetailPage(dashboard));
    }
}
