from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator


def paginate(request, items, per_page=25, param="page"):
    paginator = Paginator(items, per_page)
    try:
        return paginator.page(request.GET.get(param, 1))
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)
