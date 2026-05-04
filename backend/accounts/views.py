from __future__ import annotations

from django.contrib.auth import authenticate, login, logout
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import CurrentUserSerializer, LoginSerializer, RegisterSerializer


class SessionRegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        return Response(CurrentUserSerializer(user).data, status=status.HTTP_201_CREATED)


class SessionLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({"code": "invalid_credentials", "message": "ログインに失敗しました。"}, status=status.HTTP_400_BAD_REQUEST)

        login(request, user)
        return Response(CurrentUserSerializer(user).data)


class SessionLogoutView(APIView):
    def post(self, request: Request) -> Response:
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    def get(self, request: Request) -> Response:
        return Response(CurrentUserSerializer(request.user).data)

# Create your views here.
