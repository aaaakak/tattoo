"""
Shop models: prints, posters, originals, merchandise, digital products.

Order/OrderItem are a SKELETON: the schema is stable so a payment provider can be added
later without a migration on live data. There is no checkout and no provider wired in --
and no button in the UI that pretends to charge anyone. See docs/erd.md section 8.
"""

from __future__ import annotations

from django.db import models
from django.utils.text import slugify

from apps.core.models import (
    MediaAsset,
    PublishableModel,
    PublishedManager,
    SEOMixin,
    TimeStampedModel,
)


class ProductCategory(TimeStampedModel):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, db_index=True)
    description = models.TextField(blank=True)
    cover = models.ForeignKey(
        MediaAsset, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    order = models.PositiveSmallIntegerField(default=0)
    is_featured = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "product categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(PublishableModel, SEOMixin):
    class Type(models.TextChoices):
        PRINT = "print", "Print"
        POSTER = "poster", "Poster"
        ORIGINAL = "original", "Original artwork"
        MERCH = "merch", "Merchandise"
        DIGITAL = "digital", "Digital download"

    class Availability(models.TextChoices):
        IN_STOCK = "in_stock", "In stock"
        MADE_TO_ORDER = "made_to_order", "Made to order"
        SOLD_OUT = "sold_out", "Sold out"
        COMING_SOON = "coming_soon", "Coming soon"

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, db_index=True)
    description = models.TextField(blank=True)

    category = models.ForeignKey(
        ProductCategory, on_delete=models.PROTECT, related_name="products"
    )
    product_type = models.CharField(max_length=20, choices=Type.choices, default=Type.PRINT)

    price = models.DecimalField(max_digits=9, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")

    stock = models.PositiveIntegerField(
        null=True, blank=True, help_text="Leave empty for made-to-order / unlimited."
    )
    is_limited = models.BooleanField(default=False)
    edition_size = models.PositiveSmallIntegerField(null=True, blank=True)

    availability = models.CharField(
        max_length=20, choices=Availability.choices,
        default=Availability.IN_STOCK, db_index=True,
    )
    is_featured = models.BooleanField(default=False, db_index=True)
    tags = models.ManyToManyField("core.Tag", blank=True, related_name="products")

    objects = PublishedManager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gte=0), name="product_price_non_negative"),
            models.CheckConstraint(
                condition=models.Q(stock__isnull=True) | models.Q(stock__gte=0),
                name="product_stock_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "is_featured"]),
            models.Index(fields=["category", "status"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def is_orderable(self) -> bool:
        """Honest orderability -- never claims availability the stock does not support."""
        if self.availability in {self.Availability.SOLD_OUT, self.Availability.COMING_SOON}:
            return False
        return self.stock is None or self.stock > 0

    def get_absolute_url(self) -> str:
        from django.urls import reverse

        return reverse("shop:detail", kwargs={"slug": self.slug})


class ProductImage(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    asset = models.ForeignKey(
        MediaAsset, on_delete=models.PROTECT, related_name="product_images"
    )
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["product", "order"], name="uniq_productimage_order"),
            models.UniqueConstraint(
                fields=["product"], condition=models.Q(is_primary=True),
                name="uniq_product_primary_image",
            ),
        ]

    def __str__(self):
        return self.caption or f"Image {self.order} of {self.product.name}"
