
"""Common tacl internal config."""

API_VERSION = 'v1'
PROD = 'https://api.tsd.usit.no' + '/' + API_VERSION
TEST = 'https://test.api.tsd.usit.no' + '/' + API_VERSION
ENV = {'test': TEST, 'prod': PROD}
# Note: these keys by themselves do not allow the client to do anything
# they have to be combined with credentials to allow any API operations
# the only thing they enable is being able to revoke access from an app
API_KEYS = {
    'test': 'eyJhbGciOiJBMjU2S1ciLCJlbmMiOiJBMjU2Q0JDLUhTNTEyIn0.ug4LHXR5kcsVg5tVUl2UvNqGBJYM4jk0t3LkwtuALqQhTQE2BsvGaLoLPZsQZPxpJRIdFwMxYgSjxJ5lc5TfTuth_K9jCllu.gCW1MMhUhiEjSqhCLIBmJg.J88BprVTK9hhoNwaBarlbfg5Vq5uimelPxOcfYfAtjb_LJqTqUnFJrFhd_vqDGHSamlJmL2zLXUCwTObTEMCJakqElbIl_TcNZxsFViZ5bUa6wtc_0_59qmNm6Zx8E26-Ocph4t2NdDDpSx7137VGUcS62ZdFEWq8qP5Q028EvM.CQR3sOL1SizLKU4E07WLFhwZ04rjD-8t_n-9LKYbc3k',
    'prod': 'eyJhbGciOiJBMjU2S1ciLCJlbmMiOiJBMjU2Q0JDLUhTNTEyIn0.mei3xPmfKSJ1wwlUpVhEIqEioaaihWpAYQctsTD6SYoPBveyGGIO1wHk2_wmd8hXldF1cYRulxenOvRGJQGKbb6PPqXz9Qqz.5bJ1AU18jPkrLzVw2_29_A.k-3ZPAWvtKMLnFSUGyhZow6DSlbuvKBTNvbH4byZGreaSEGLgmKTJy84joei5Lafn537FD4IBOGWARysACzz5ovL5xhqgmolyJFQ2kKFnrpAbUdrpcT55mII-EtzEM6OKyCL3Lep9QYnqSX0vSorof3lZSrHB29Teb9SZ6pS6zE.H3Zon0lL4v8a4kHyMO5ZclYr1nZzzAQxY4z5Ilw2WhY'
}
