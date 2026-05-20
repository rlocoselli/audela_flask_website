using AudelaMobileLight.Models;

namespace AudelaMobileLight.Pages;

public partial class ProductDetailPage : ContentPage
{
    public AudelaProduct Product { get; }

    public ProductDetailPage(AudelaProduct product)
    {
        InitializeComponent();
        Product = product;
        Title = product.Title;
        BindingContext = this;
    }
}
