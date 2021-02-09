from django.shortcuts import render
from django.http import HttpResponse
from rango.models import Category, Page, UserProfile  
from rango.forms import CategoryForm,  PageForm, UserForm, UserProfileForm
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from datetime import datetime

# This retrieves a given cookie for a session that is stored SERVER-SIDE.
# Helper function for all other cookies. 
def get_server_side_cookie(request, cookie, default_val=None):
    val = request.session.get(cookie)
    if not val:
        val = default_val
    return val

# This is a cookie helper function: NOT  a view. It counts the ammount of visits a client makes (max 1 per day).
# This stores cookies on the server-side with the above helper function, meaning there is no reason to receive 
# or change a response.
def visitor_cookie_handler(request): 
    # We use the get_server_side_cookie helper function to get the visits cookie.
    # If the cookie exists, the value returned is casted to an integer.
    # If the cookie doesn't exist, then the default value of 1 is used.
    visits = int(get_server_side_cookie(request, 'visits', '1'))

    # the last_visit_cookie tracks the datetime of the last visit. If there isn't one, it is the current datetime.
    # last_visit_time is the stripped datetime of last_visit_cookie, which is used to calculate the time since last visit.
    # Check datetime docs for details on how datetime works. 
    last_visit_cookie = get_server_side_cookie(request, 'last_visit', str(datetime.now()))
    last_visit_time = datetime.strptime(last_visit_cookie[:-7], '%Y-%m-%d %H:%M:%S')

    # If it's been more than a day since the last visit, increment visits cookie and set the session cookie (server-side) 
    # to make the last visit now. Else, we set the last_visit cookie to the same value it already had. 
    if (datetime.now() - last_visit_time).days > 0:
        visits = visits + 1
        request.session['last_visit'] = str(datetime.now())
    else:
        request.session['last_visit'] = last_visit_cookie

    # finally, update/set the visits cookie. 
    request.session['visits'] = visits


def index(request):
    # Query the database for a list of ALL categories currently stored.
    # Order the categories by the number of likes in descending order.
    # Retrieve the top 5 only -- or all if less than 5.
    # Place the list in our context_dict dictionary (with our boldmessage!)
    # that will be passed to the template engine.
    category_list = Category.objects.order_by('-likes') [:5]
    page_list = Page.objects.order_by('-views') [:5]

    # handle the cookies
    visitor_cookie_handler(request)
    context_dict = {}
    context_dict['boldmessage'] = 'Crunchy, creamy, cookie, candy, cupcake!'
    context_dict['categories'] = category_list
    context_dict['pages'] = page_list
    return render(request, 'rango/index.html', context=context_dict)


def about(request):
    # The about page now shows the visits, but there may be a case when the about page is 
    # accessed without ever visiting the index, so we should count visits here too. 
    visitor_cookie_handler(request)
    context_dict = {'boldmessage': 'This tutorial has been put together by 2469283B'}
    context_dict['visits'] = request.session['visits']

    if request.session.test_cookie_worked():
        print("TEST COOKIE WORKED!")
        request.session.delete_test_cookie()

    return render(request,"rango/about.html", context = context_dict)

def show_category(request, category_name_slug):
    context_dict = {}

    # Can we find a category name slug with the given name?
    # If we can't, the .get() method raises a DoesNotExist exception.
    # The .get() method returns one model instance or raises an exception.
    try:
        category = Category.objects.get(slug=category_name_slug)

        pages = Page.objects.filter(category=category)

        context_dict['pages'] = pages
        context_dict['category'] = category

    # We get here if we didn't find the specified category.
    # Don't do anything -
    # the template will display the "no category" message for us.
    except Category.DoesNotExist:
        context_dict['pages'] = None
        context_dict['category'] = None

    return render(request, 'rango/category.html', context = context_dict)

@login_required
def add_category(request):
    form = CategoryForm()

    if request.method == 'POST':
        form = CategoryForm(request.POST)

        if form.is_valid():
            form.save(commit=True)
            return redirect('/rango/')
        else:
            print(form.errors)

    return render(request, 'rango/add_category.html', {'form': form})

@login_required
def add_page(request, category_name_slug):
    try:
        category = Category.objects.get(slug=category_name_slug)
    except Category.DoesNotExist:
        category = None

    if category is None:
        return redirect('/rango/')
    
    form = PageForm()

    if request.method == 'POST':
        form = PageForm(request.POST)

        if form.is_valid():
            if category:
                page = form.save(commit=False)
                page.category = category
                page.views = 0
                page.save()

                return redirect(reverse('rango:show_category', kwargs={'category_name_slug': category_name_slug}))
        else:
            print(form.errors)

    context_dict = {'form': form, 'category': category}
    return render(request, 'rango/add_page.html', context=context_dict)

def register(request):
    # boolean to tell template if register was successful. set to false initially
    registered = False

    if request.method =='POST':
        user_form = UserForm(request.POST)
        profile_form = UserProfileForm(request.POST)

        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()

            # this method hashes the password and then we can save user
            user.set_password(user.password)
            user.save()

            # Now the UserProfile instance. set commit to false to delay model saving
            # until we're ready
            profile = profile_form.save(commit=False)
            profile.user = user

            # check if profile picture was set
            if 'picture' in request.FILES:
                profile.picture = request.FILES['picture'] 
            
            profile.save()

            # update registered as registration was successful
            registered = True
        
        else:
            # invalid form? 
            print(user_form.errors, profile_form.errors)
    else:
        # not POST request, so render form using two ModelForm instances
        # These forms will be blank and ready for input.
        user_form = UserForm()
        profile_form = UserProfileForm()

    # Render template depending on context
    return render(request, 'rango/register.html', context = {'user_form': user_form,
                                                            'profile_form': profile_form,
                                                            'registered': registered})

def user_login(request):
    if request.method == 'POST':

        # gather pword and username from user
        username = request.POST.get('username')
        password = request.POST.get('password')

        # django machinery checks if user/pword corresponds to user. If it does, returns a user object
        user = authenticate(username=username, password=password)

        # if login details are correct
        if user:

            # check if account is disabled
            if user.is_active:

                # login the user and redirect to index page
                login(request, user)
                return redirect(reverse('rango:index'))
            else:

                # deactivated account can't be logged in 
                return HttpResponse("Your Rango account is disabled.")
        else:

            # wrong login details 
            print(f"Invalid logic details: {username}, {password}")
            return HttpResponse("Invalid login details supplied.")

    else:

        # in the case of a GET request, we post the form (no context variables needed)
        return render(request, 'rango/login.html')

@login_required
def user_logout(request):
    logout(request)
    # take the user to homepage
    return redirect(reverse('rango:index'))

@login_required
def restricted(request):
    return render(request, 'rango/restricted.html')