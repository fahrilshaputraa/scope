from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from .documentation import ARTICLES, search_articles
from .permissions import can_create_project


def article_url(item):
    if item["slug"] == "mengenal-scope":
        return reverse("identity:docs")
    return reverse("identity:docs_article", args=[item["slug"]])


@login_required
@require_GET
def documentation_view(request, slug="mengenal-scope"):
    current = next((item for item in ARTICLES if item["slug"] == slug), None)
    if current is None:
        raise Http404("Topik dokumentasi tidak ditemukan.")
    query = " ".join(request.GET.get("q", "").split())[:200]
    groups = {}
    for item in ARTICLES:
        groups.setdefault(item["group"], []).append({**item, "url": article_url(item)})
    results = (
        [{**match, "url": article_url(match["article"])} for match in search_articles(query)]
        if query
        else []
    )
    position = ARTICLES.index(current)
    previous = ARTICLES[position - 1] if position > 0 else None
    following = ARTICLES[position + 1] if position < len(ARTICLES) - 1 else None
    action = current.get("action")
    action_link = None
    if action and (not current.get("manage_action") or can_create_project(request.user)):
        action_link = {"url": reverse(action[0]), "label": action[1]}
    return render(
        request,
        "identity/docs.html",
        {
            "article": current,
            "docs_groups": groups.items(),
            "article_count": len(ARTICLES),
            "query": query,
            "search_results": results,
            "action_link": action_link,
            "previous_article": {**previous, "url": article_url(previous)} if previous else None,
            "next_article": {**following, "url": article_url(following)} if following else None,
            "related_articles": [
                {**item, "url": article_url(item)}
                for item in ARTICLES
                if item["slug"] in current.get("related", [])
            ],
        },
    )
