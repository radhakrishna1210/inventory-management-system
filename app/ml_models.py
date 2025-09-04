# FILE: app/ml_models.py
import pandas as pd
from sklearn.linear_model import LinearRegression
import joblib

# CORRECTED: Removed imports for sqlalchemy and flask

def get_sales_data(engine): # CORRECTED: Accepts the database engine as a parameter
    """Fetches sales data and aggregates it by day."""
    # CORRECTED: Uses the provided engine
    query = "SELECT b.date, bi.quantity FROM bill b JOIN bill_item bi ON b.id = bi.bill_id;"
    df = pd.read_sql(query, engine)
    
    if df.empty:
        return pd.DataFrame(columns=['ds', 'y'])

    df['date'] = pd.to_datetime(df['date'])
    daily_sales = df.groupby(df['date'].dt.date)['quantity'].sum().reset_index()
    daily_sales.columns = ['ds', 'y'] 
    return daily_sales

def train_and_save_demand_model(engine): # CORRECTED: Accepts the engine
    """Trains a simple regression model and saves it to a file."""
    df = get_sales_data(engine) # CORRECTED: Passes the engine along
    
    if len(df) < 2: 
        print("Not enough data to train a demand model.")
        return None

    df['ds'] = pd.to_datetime(df['ds'])
    df['time_index'] = (df['ds'] - df['ds'].min()).dt.days
    
    X = df[['time_index']]
    y = df['y']
    
    model = LinearRegression()
    model.fit(X, y)
    
    joblib.dump(model, 'demand_model.pkl')
    print("Demand model trained and saved as demand_model.pkl")
    return model

def predict_future_demand(engine): # CORRECTED: Accepts the engine
    """Loads the model and predicts demand for the next 30 days."""
    try:
        model = joblib.load('demand_model.pkl')
    except FileNotFoundError:
        print("Model not found. Training a new one.")
        model = train_and_save_demand_model(engine) # CORRECTED: Passes the engine
        if model is None:
            return "Not enough data to forecast."

    df = get_sales_data(engine) # CORRECTED: Passes the engine
    if df.empty:
        last_time_index = -1
    else:
        df['ds'] = pd.to_datetime(df['ds'])
        last_time_index = (df['ds'].max() - df['ds'].min()).days

    future_indices = pd.DataFrame({'time_index': range(last_time_index + 1, last_time_index + 31)})
    
    predictions = model.predict(future_indices)
    
    total_predicted_demand = max(0, int(sum(predictions)))
    return total_predicted_demand