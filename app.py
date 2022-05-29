import os
import pathlib
import pandas as pd
import ast
from requests import session
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import requests
from flask import Flask, session, abort,render_template, redirect, request
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests

# load the data from the csv file to a pandas dataframe
movies = pd.read_csv('tmdb_5000_movies.csv')
credits = pd.read_csv('tmdb_5000_credits.csv')
movies = movies.merge(credits,on='title')
# selecting the features for recommendation
movies = movies[['movie_id','title','overview','genres','keywords','cast','crew']]
def convert(text):
    L = []
    for i in ast.literal_eval(text):
        L.append(i['name'])
    return L
movies.dropna(inplace=True)
movies['genres'] = movies['genres'].apply(convert)
movies['keywords'] = movies['keywords'].apply(convert)
def convert3(text):
    L = []
    counter = 0
    for i in ast.literal_eval(text):
        if counter < 3:
            L.append(i['name'])
        counter+=1
    return L
movies['cast'] = movies['cast'].apply(convert)
movies['cast'] = movies['cast'].apply(lambda x:x[0:3])
def fetch_director(text):
    L = []
    for i in ast.literal_eval(text):
        if i['job'] == 'Director':
            L.append(i['name'])
    return L
movies['crew'] = movies['crew'].apply(fetch_director)
def collapse(L):
    L1 = []
    for i in L:
        L1.append(i.replace(" ",""))
    return L1
movies['keywords'] = movies['keywords'].apply(collapse)
movies['overview'] = movies['overview'].apply(lambda x:x.split())
# combining all selected features
movies['tags'] = movies['overview'] + movies['genres'] + movies['keywords'] + movies['cast'] + movies['crew']
movies['tags'] = movies['tags'].apply(lambda x: " ".join(x))
cv = CountVectorizer(max_features=5000,stop_words='english')
vector = cv.fit_transform(movies['tags']).toarray()
# get the similarity scores using cosine similarity
similarity = cosine_similarity(vector)
movies['overview'] = movies['overview'].apply(lambda x: " ".join(x))
movies['genres'] = movies['genres'].apply(lambda x: ", ".join(x))
movies['cast'] = movies['cast'].apply(lambda x: ", ".join(x))
movies['crew'] = movies['crew'].apply(lambda x: ", ".join(x))



def fetch_poster(movie_id):
    response = requests.get(
        'https://api.themoviedb.org/3/movie/{}?api_key=1de258408913c3801da46e5e75a8e7ea&language=en-US'.format(
            movie_id))
    data = response.json()
    return "https://image.tmdb.org/t/p/original/" + data['poster_path']


def recommend(movie):
    movie_index = movies[movies['title'] == movie].index[0]
    distances = similarity[movie_index]
    # sorting the movies based on their similarity score
    movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:9]
    recommended_movies = []
    recommended_movies_posters = []
    recommended_movies_genre = []
    recommended_movies_cast = []
    recommended_movies_overview = []
    for i in movies_list:
        movie_id = movies.iloc[i[0]].movie_id
        recommended_movies.append(movies.iloc[i[0]].title)
        recommended_movies_genre.append(movies.iloc[i[0]].genres)
        recommended_movies_cast.append(movies.iloc[i[0]].cast)
        recommended_movies_overview.append(movies.iloc[i[0]].overview)
        recommended_movies_posters.append(fetch_poster(movie_id))
    return recommended_movies, recommended_movies_genre, recommended_movies_cast, recommended_movies_overview, recommended_movies_posters



app = Flask(__name__)
app.secret_key = 'manisha0321'

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

GOOGLE_CLIENT_ID = "984154832820-73j1m8n9rndo1qi1usnrptg6sl0649gv.apps.googleusercontent.com"

client_secret_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")

# holding infomation of how to authorize users
flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secret_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email",
            "openid"],
    redirect_uri="http://localhost:5000/callback"
)


def login_is_required(function):
    def wrapper(*args, **kwargs):
        if "google_id" not in session:
            abort(401)  # authentication required

        else:
            return function()

    return wrapper


@app.route("/",methods=['POST', 'GET'])
def home():
    if request.method == "POST":
        return redirect("/login")
    return render_template("home.html")


@app.route("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session["state"] == request.args["state"]:
        abort(500)  # State does not match!

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )

    session["google_id"] = id_info.get("sub")
    session["name"] = id_info.get("name")
    return redirect("/main")


@app.route("/login")
def login():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)


@app.route("/logout",methods=['POST', 'GET'])
def logout():
    if request.method == "GET":
     session.clear()
    return redirect("/")



@app.route("/main", methods=['POST', 'GET'])
@login_is_required
def main():
    if request.method == "POST":
        selected_movie = request.form.get("fname")
        try:
            names, genre, cast, overview, posters = recommend(selected_movie)
        except:
            f = open(".\\templates\\index.html", "r")
            old_text = f.read()
            new_text = old_text.replace("Result",
                                        "<h7>Oops!!!<br>We could not find a match! Please try with other movie name.")
            return new_text
        x = " "
        y = " "
        j = 0
        for i in names:
            x = "<p><br clear = \"left\" ><img src=\"" + posters[
                j] + "\" align=\"right\" border = \"3px\" width=\"481\" height=\"721\"/><h2>" + i + "<br><br><h3>Genre:<h6>" + \
                genre[j] + "<h3>Cast:<h6>" + cast[j] + "<h3>Overview:<h6>" + overview[
                    j] + "<br><h3>Do you like this movie?&nbsp&nbsp<form action=\"/main\" class=\"grid\" method=\"POST\"><input id=\"movie\" name=\"fname\" type=\"hidden\" value=\"" + i + "\"/><button type=\"submit\"><img src=\"https://th.bing.com/th/id/OIP.l_3IZDAnM9URIDtL9mQvCgHaHa?w=205&h=205&c=7&r=0&o=5&dpr=1.25&pid=1.7\" height =\"50\" width=\"50\" alt=\"Like\"/></button></form>" + "</p><br><br><br>"
            y = y + x
            j = j + 1
        y = y + " "
        f = open(".\\templates\\index.html", "r")
        old_text = f.read()
        new_text = old_text.replace("Result", y)
        try:
            new_text = new_text.replace("Welcome!", "Welcome "+session["name"]+"!")
        except:
            print(session["name"])
        return new_text
    return render_template('index.html')

if __name__ == "__main__":
    app.run(debug=True)
