# api/serializers.py
import base64
from multiprocessing import Value

from django.core.files.base import ContentFile
from rest_framework import serializers

from recipes.models import Tag, Recipe, RecipeIngredient, Ingredient
from users.models import CustomUser, Subscription


class Base64ImageField(serializers.ImageField):
    """Serializer поля image"""
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            img_format, img_str = data.split(';base64,')
            ext = img_format.split('/')[-1]
            data = ContentFile(base64.b64decode(img_str), name='img.' + ext)

        return super().to_internal_value(data)


class RecipeMinifiedSerializer(serializers.ModelSerializer):

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = ('id',)


class CustomUserSerializer(serializers.ModelSerializer):
    """Serializer модели CustomUser"""
    is_subscribed = serializers.SerializerMethodField(method_name='is_subscribed_user')
    recipes = RecipeMinifiedSerializer(many=True, read_only=True)
    recipes_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CustomUser
        fields = ('id', 'email', 'username', 'first_name', 'last_name',
                  'is_subscribed', 'recipes', 'recipes_count')
        read_only_fields = ('id',)

    def is_subscribed_user(self, obj):
        request = self.context.get("request")
        is_subscribed = request.query_params.get("is_subscribed", False)

        if is_subscribed:
            user = request.user
            subscribed = user.following.filter(pk=obj.pk).exists()
            return subscribed
        else:
            return False


def always_true(*args, **kwargs):
    return True


class SubscriptionSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.BooleanField(default=True)

    class Meta:
        model = CustomUser
        fields = ('id', 'email', 'username', 'first_name', 'last_name', 'is_subscribed', 'recipes')

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        recipes_limit = int(self.context.get('recipes_limit', 0))

        if recipes_limit is not None:
            recipes_queryset = instance.recipes.all()[:recipes_limit]
        else:
            recipes_queryset = instance.recipes.all()

        representation['recipes'] = RecipeMinifiedSerializer(recipes_queryset, many=True).data
        return representation


class CustomUserSignUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'email', 'username', 'first_name', 'last_name', 'password')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        password = validated_data.pop('password')
        instance = super().create(validated_data)
        instance.set_password(password)
        instance.save()
        return instance


class TagSerializer(serializers.ModelSerializer):
    """Serializer модели Tag"""

    class Meta:
        model = Tag
        fields = ('id', 'name', 'color', 'slug')


class RecipeIngredientSerializer(serializers. ModelSerializer):
    """Serializer модели RecipeIngredient"""
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.CharField(source='ingredient.name')
    measurement_unit = serializers.CharField(source='ingredient.measurement_unit')

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeSerializer(serializers.ModelSerializer):
    """Serializer модели Recipe"""
    tags = TagSerializer(many=True)
    ingredients = RecipeIngredientSerializer(many=True, source='recipe_ingredients')
    image = Base64ImageField()
    author = CustomUserSerializer(read_only=True)

    class Meta:
        model = Recipe
        exclude = ('pub_date',)

    def get_ingredients(self, instance):
        return RecipeIngredientSerializer(
            instance.recipe_ingredients.all(),
            many=True
        ).data


class RecipeIngredientCreateSerializer(serializers.ModelSerializer):
    """Serializer создания объектов в модели RecipeIngredient"""
    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(),
        source='ingredient'
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'amount')





class RecipeCreateSerializer(serializers.ModelSerializer):
    """Serializer создания объектов в модели Recipe"""
    ingredients = RecipeIngredientCreateSerializer(many=True)

    class Meta:
        model = Recipe
        fields = (
            'name',
            'cooking_time',
            'text', 'tags',
            'ingredients',
            'image',
            'pub_date'
        )

    def create(self, validated_data):
        author = self.context.get('request').user
        ingredients = validated_data.pop('ingredients')
        instance = super().create(validated_data)
        for ingredient_data in ingredients:
            RecipeIngredient(
                recipe=instance,
                ingredient=ingredient_data['ingredient'],
                amount=ingredient_data['amount']
            ).save()
        return instance

    def to_representation(self, instance):
        return RecipeSerializer(instance).data
