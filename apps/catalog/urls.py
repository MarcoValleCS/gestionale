from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.ProductListView.as_view(), name="product_list"),
    path("nuovo/", views.ProductCreateView.as_view(), name="product_create"),
    path("categorie/", views.CategoryListView.as_view(), name="category_list"),
    path("categorie/nuova/", views.CategoryCreateView.as_view(), name="category_create"),
    path("categorie/<int:pk>/", views.CategoryUpdateView.as_view(), name="category_update"),
    path("<int:pk>/", views.ProductDetailView.as_view(), name="product_detail"),
    path("<int:pk>/modifica/", views.ProductUpdateView.as_view(), name="product_update"),
    path("<int:pk>/default/", views.product_defaults, name="product_defaults"),
]
