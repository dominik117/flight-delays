import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats

@st.cache_data
def load_data():
    df = pd.read_csv('data/airline_delay.csv')
    df = df.dropna(axis=0).reset_index(drop=True)
    return df

@st.cache_data
def load_airport_data():
    df_airports = pd.read_csv('data/us-airports.csv')
    df_airports = df_airports.drop(df_airports.index[0]).reset_index(drop=True)
    df_airports2 = pd.read_csv('data/airports.csv')
    df_airports2.rename(columns={'LATITUDE':'latitude_deg', 'LONGITUDE':'longitude_deg', 'AIRPORT':'name', 'STATE':'local_region', 'CITY':'municipality'}, inplace=True)
    df_airports2.drop(columns=['COUNTRY'], inplace=True)
    return df_airports, df_airports2


df = load_data()
df['carrier_name'] = df['carrier_name'].astype('category')

df_airports, df_airports2 = load_airport_data()

st.markdown("""
<style>
.title {
    color: #CF0A2C;
    font-size: 48px;
    font-weight: bold;
}
.subtitle {
    color: #333333;
    font-size: 24px;
    margin-bottom: 20px;
}
</style>
<div class='title'>US Airlines Delay Analysis</div>
<div class='subtitle'>An overview of flight delays from US domestic passenger flights in December 2019 and December 2020</div>
""", unsafe_allow_html=True)

st.markdown("<hr style='border:2px solid #CF0A2C;'>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

st.write(f"### Filter the Airline Plots")

# year and metrics
col1, col2 = st.columns(2)
year = col1.selectbox('Select Year', options=['Both Years', 2019, 2020])
if year != 'Both Years':
    df = df[df['year'] == int(year)]

option = col2.selectbox('Select Metric', ('Percentage of Delays', 'Total Delays', 'Average Time Delay', 'Total Flights'))



st.markdown('<p style="font-size:14px;">Select Type of Delay</p>', unsafe_allow_html=True)
# delay reasons
with st.container():
    cols = st.columns(5)
    reasons = ['Carrier', 'Weather', 'National Aviation Traffic', 'Security Breach', 'Previous Flight Delayed']
    selected_reasons = []
    for i, reason in enumerate(reasons):
        if cols[i].checkbox(reason, True, key=reason):
            selected_reasons.append(reason)
reason_mapping = {
    'Carrier': ['carrier_ct', 'carrier_delay'],
    'Weather': ['weather_ct', 'weather_delay'],
    'National Aviation Traffic': ['nas_ct', 'nas_delay'],
    'Security Breach': ['security_ct', 'security_delay'],
    'Previous Flight Delayed': ['late_aircraft_ct', 'late_aircraft_delay']
}

st.markdown("<br>", unsafe_allow_html=True)

#####
# Data processing for maps
df_full = pd.merge(df, df_airports[['local_code', 'latitude_deg', 'longitude_deg', 'name', 'local_region', 'municipality']], left_on='airport', right_on='local_code', how='left')
df_full = pd.merge(df_full, df_airports2, left_on='airport', right_on='IATA', how='left', suffixes=('', '_2'))

for column in df_airports2.columns:
    if column == "IATA":
        continue
    df_full[column] = df_full[column].fillna(df_full[column+"_2"])
df_full.drop([x+"_2" for x in df_airports2.columns if x != "IATA"], axis=1, inplace=True)

airport_delays_agg = df_full.groupby('airport').agg({
    'arr_flights': 'sum',
    'arr_del15': 'sum',
    'arr_delay': 'sum'
}).reset_index()

airport_delays_agg.rename(columns={'arr_flights': 'arr_flights_sum', 'arr_del15': 'arr_del15_sum', 'arr_delay': 'arr_delay_sum'}, inplace=True)

airport_delays_agg['delay_percentage'] = (airport_delays_agg['arr_del15_sum'] / airport_delays_agg['arr_flights_sum']) * 100
airport_delays_agg['delay_time_average'] = (airport_delays_agg['arr_delay_sum'] / airport_delays_agg['arr_del15_sum'])

airport_delays = pd.merge(df_full, airport_delays_agg, on='airport', how='left')
airport_delays.dropna(subset=['delay_time_average', 'delay_percentage'], inplace=True)

z_scores = stats.zscore(airport_delays['delay_percentage'])
airport_delays = airport_delays[(z_scores < 3.5)]

z_scores = stats.zscore(airport_delays['delay_time_average'])
airport_delays = airport_delays[(z_scores < 3.5)]

airport_delays['scaled_delay_average'] = np.log1p(airport_delays['delay_time_average'])
airport_delays['scaled_delay_percentage'] = np.log1p(airport_delays['delay_percentage'])

airport_delays.dropna(inplace=True)
###########

# BAR PLOT
def create_plot(data, x, y, title, xlabel, ylabel):
    fig = px.bar(data, x=x, y=y, text=x, hover_data=[x], orientation='h')
    fig.update_traces(
        texttemplate='%{x:,.0f}', 
        textposition='inside', 
        marker_color='#CF0A2C', 
        textfont=dict(color='white'),
        textangle=0
    )
    fig.update_layout(
        title=title, 
        xaxis_title=xlabel, 
        yaxis_title=ylabel, 
        font=dict(size=18), 
        margin=dict(l=20, r=20, t=40, b=40), 
        autosize=True, 
        width=1000
    )
    return fig

# SCATTER PLOT
def create_scatter_plot(data, reasons):
    selected_counts = data[reason_mapping[reasons[0]][0]].copy()
    selected_delays = data[reason_mapping[reasons[0]][1]].copy()
    for reason in reasons[1:]:
        selected_counts += data[reason_mapping[reason][0]]
        selected_delays += data[reason_mapping[reason][1]]
    data['selected_counts'] = selected_counts
    data['selected_delays'] = selected_delays

    carrier_delays = data.groupby('carrier_name', observed=True).agg({
        'arr_flights': 'sum',
        'selected_counts': 'sum',
        'selected_delays': 'sum'
    }).reset_index()
    carrier_delays['delay_percentage'] = (carrier_delays['selected_counts'] / carrier_delays['arr_flights']) * 100
    carrier_delays['delay_average'] = (carrier_delays['selected_delays'] / carrier_delays['selected_counts'])
    carrier_delays = carrier_delays.dropna(subset=['delay_percentage', 'delay_average'])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=carrier_delays['delay_percentage'],
        y=carrier_delays['delay_average'],
        text=carrier_delays['carrier_name'],
        mode='markers',
        marker=dict(
            size=13,
            color=carrier_delays['delay_percentage'],
            colorscale='RdYlGn_r',
            showscale=False,
            line=dict(width=2, color='black') 
        ),
        textposition='top center',
        hovertemplate=(
            '<b>%{text}</b><br>' +
            'Delay Percentage: %{x:.1f}%<br>' +
            'Average Delay: %{y:.1f} minutes<extra></extra>'
        )
    ))

    median_delay_percentage = carrier_delays['delay_percentage'].median()
    median_delay_average = carrier_delays['delay_average'].median()
    
    fig.add_vline(x=median_delay_percentage, line=dict(color='red', dash='dash'))
    fig.add_hline(y=median_delay_average, line=dict(color='red', dash='dash'))
    
    fig.update_layout(
        title='Delay Performance Matrix',
        xaxis_title='Percentage of Delayed Flights (%)',
        yaxis_title='Average Time Delay (minutes)',
        font=dict(size=18), 
        margin=dict(l=20, r=20, t=40, b=40), 
        autosize=True, 
        width=1000,
        yaxis=dict(autorange='reversed'),
        xaxis=dict(autorange='reversed')
    )
    return fig


# PIE CHART
def create_pie_chart(data, airline):
    if airline != 'All Airlines':
        data = data[data['carrier_name'] == airline]

    delay_types = ['carrier_ct', 'weather_ct', 'nas_ct', 'security_ct', 'late_aircraft_ct']
    reason_labels = list(reason_mapping.keys())
    total_delays = data['arr_del15'].sum()
    delay_percentages = [(data[delay].sum() / total_delays * 100) for delay in delay_types]

    fig = go.Figure(data=[go.Pie(labels=reason_labels, values=delay_percentages, hole=.3)])
    fig.update_layout(title_text=f'Percentage of Delay Types for {airline}',
                      legend_title_text='Delay Reasons',
                      legend=dict(
            title=dict(
                text='Delay Reasons',
                font=dict(size=18)  
            ),
            font=dict(size=16) 
        ))
    return fig


# SCATTER MAP
def make_scatter_map(size, color, title):
    fig = go.Figure()

    fig.add_trace(go.Scattergeo(
        lon = airport_delays['longitude_deg'],
        lat = airport_delays['latitude_deg'],
        text = airport_delays['name'] + '<br>Delay Average: ' + airport_delays['delay_time_average'].round(1).astype(str) + 
            '<br>Delay Percentage: ' + airport_delays['delay_percentage'].round(1).astype(str),

        marker = dict(
            size = airport_delays[size], 
            color = airport_delays[color],
            colorscale = 'RdYlGn_r',
            colorbar_title = '',
            line_color='grey',
            sizemode = 'area',
            sizeref = airport_delays[size].max() / 350, 
            sizemin = 3.5  # minimum marker size
        ),
        hoverinfo='text'
    ))

    fig.update_geos(
        resolution=110,
        showcountries=True, 
        landcolor="beige",
        countrycolor="black",
        subunitcolor="grey"
    )

    fig.update_layout(
        title=dict(text=title, x=0.5),
        geo=dict(
            scope='usa',
            projection_type='albers usa',
            lakecolor='#E5E4E2',
            bgcolor='rgba(255,255,255,0.8)'
        ),
        margin=dict(l=0, r=0, t=40, b=10),
        width=1000,
        height=500
    )
    return fig



#################### DASHBOARD ####################
st.markdown("<hr style='border:2px solid #CF0A2C;'>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

if not selected_reasons:
    st.error('Please select at least one reason for delay.')
else:
    st.write(f"### Overview of {option}")

    if option == 'Total Flights':
        metric = df.groupby('carrier_name', observed=True)['arr_flights'].sum().reset_index().sort_values('arr_flights', ascending=True)
        fig = create_plot(metric, 'arr_flights', 'carrier_name', 'Total Flights', 'Number of Flights', 'Carrier Name')
        st.plotly_chart(fig, use_container_width=True)


    elif option in ['Total Delays', 'Percentage of Delays', 'Average Time Delay']:
        selected_counts = df[reason_mapping[selected_reasons[0]][0]].copy()
        selected_delays = df[reason_mapping[selected_reasons[0]][1]].copy()
        
        
        for reason in selected_reasons[1:]:
            selected_counts += df[reason_mapping[reason][0]]
            selected_delays += df[reason_mapping[reason][1]]
        df['selected_counts'] = selected_counts
        df['selected_delays'] = selected_delays

        if option == 'Total Delays':
            metric = df.groupby('carrier_name', observed=True)['selected_counts'].sum().reset_index().sort_values('selected_counts', ascending=True)
            fig = create_plot(metric, 'selected_counts', 'carrier_name', 'Total Delays', 'Number of Delays', 'Carrier Name')

        elif option == 'Percentage of Delays':
            metric = df.groupby('carrier_name', observed=True).agg({'arr_flights': 'sum', 'selected_counts': 'sum'}).reset_index()
            metric['delay_percentage'] = (metric['selected_counts'] / metric['arr_flights']) * 100
            metric = metric.sort_values(by='delay_percentage', ascending=True).reset_index(drop=True)
            fig = create_plot(metric, 'delay_percentage', 'carrier_name', 'Percentage of Delays', 'Percentage of Delays (%)', 'Carrier Name')


        elif option == 'Average Time Delay':
            metric = df.groupby('carrier_name', observed=True).agg({'selected_counts': 'sum', 'selected_delays': 'sum'}).reset_index()
            metric['delay_average'] = (metric['selected_delays'] / metric['selected_counts'])
            metric = metric.sort_values(by='delay_average', ascending=True).reset_index(drop=True)
            fig = create_plot(metric, 'delay_average', 'carrier_name', 'Average Time Delay', 'Average Time Delay (minutes)', 'Carrier Name')
        
        st.plotly_chart(fig, use_container_width=True)
    

    st.write("### Airline Distribution Matrix of Delay Performance by Average Time Delay and Percentage of Delayed Flights")
    scatter_fig = create_scatter_plot(df, selected_reasons)
    st.plotly_chart(scatter_fig, use_container_width=True)


    st.write("### Percentage distribution of different types of delays")
    airline_selection = st.selectbox('Select Airline', options=['All Airlines'] + list(df['carrier_name'].cat.categories))
    pie_fig = create_pie_chart(df, airline_selection)
    st.plotly_chart(pie_fig, use_container_width=True)

    st.markdown("<hr style='border:2px solid #CF0A2C;'>", unsafe_allow_html=True)

    st.write("### Airport Delays Scatter Map")
    map_option = st.selectbox('Select Map Metric', ('Average Time Delay', 'Percentage of Delays'))
    if map_option == 'Average Time Delay':
        map_fig = make_scatter_map(size='arr_flights_sum', color='delay_time_average', title="Average Time Delay by Airport")
        color_scale_text = "Color scale: Average Time Delay (minutes)"
    else:
        map_fig = make_scatter_map(size='arr_flights_sum', color='delay_percentage', title="Flight Delays by Airport")
        color_scale_text = "Color scale: Percentage of Delays"
    st.plotly_chart(map_fig, use_container_width=True)
    st.write(color_scale_text)
