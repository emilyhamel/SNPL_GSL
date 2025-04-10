#..............................................................................#      
#........ Snowy Plover Recreation Survey Sampling Windows Generator ...........#
#
# For 2 sites, May 15-August 31, accounting for weekends, holidays, and multi-day music festivals 
#..............................................................................#

library(lubridate)
library(dplyr)
library(tidyr)

# Set working directory 
# *NOTE* (Change WD per individual user. Directory specified is the folder in which the output file will be saved)
setwd("C:/Users/emily.hamel/Box/-.Emily.Hamel Individual/GSL/SNPL")

# For reproducibility
set.seed(123)

#..............................................................................#
# Define survey period (May 15 through August 31, 2025)
start_date <- as.Date("2025-05-15")
end_date <- as.Date("2025-08-31")

# Create a data frame with all dates in the survey period
all_dates <- data.frame(
  date = seq.Date(from = start_date, to = end_date, by = "day")
)

# Add additional columns for day of week and month
all_dates <- all_dates %>%
  mutate(
    day_of_week = weekdays(date),
    month = month(date),
    month_name = month(date, label = TRUE),
    is_weekend = day_of_week %in% c("Saturday", "Sunday"),
    is_weekday = !is_weekend
  )

#..............................................................................#
# Define holidays (Memorial Day, July 4th and Pioneer Day July 24th)
holidays <- as.Date(c("2025-05-26", "2025-07-04", "2025-07-24"))

# Define music festival days
# These festivals are located at the Saltair music venue, but people tend to drift away from that area/sleep in their cars elsewhere/etc.
# So festival dates are considered at both sites
music_festivals <- as.Date(c("2025-06-13", "2025-06-14", "2025-06-20", 
                             "2025-06-21", "2025-08-08", "2025-08-09"))

# Mark holidays and festivals in the data frame
all_dates$is_holiday <- all_dates$date %in% holidays
all_dates$is_festival <- all_dates$date %in% music_festivals

# Create strata for stratified sampling
all_dates <- all_dates %>%
  mutate(
    day_type = case_when(
      is_festival ~ "Festival",
      is_holiday ~ "Holiday",
      is_weekend ~ "Weekend",
      TRUE ~ "Weekday"
    )
  )

#..............................................................................#
# Define site names
sites <- c("Saltair", "Kennecott")


# Define possible sampling hours (6 AM to 6 PM, with 2-hour windows)
# Last window starts at 6pm and ends at 8pm
sampling_hours <- seq(6, 18, by = 2) # Starting hours for 2-hour windows

#..............................................................................#
# Function to generate sampling windows with stratified approach
generate_sampling_windows <- function(dates_df, site_names, hours, num_samples_per_stratum = 3) {
  # Empty data frame to store results
  results <- data.frame(
    site = character(),
    date = character(),
    raw_date = as.Date(character()),  # Add raw date for sorting
    day = character(),
    month = character(),
    day_type = character(),
    start_time = character(),
    end_time = character(),
    stringsAsFactors = FALSE
  )
  
  # For each site
  for (site in site_names) {
    
    # For each month
    for (m in unique(dates_df$month)) {
      
      month_dates <- subset(dates_df, month == m)
      
      # For each day type (Weekday, Weekend, Holiday, Festival)
      for (day_t in unique(month_dates$day_type)) {
        
        # Get dates for this stratum
        stratum_dates <- subset(month_dates, day_type == day_t)
        
        # Skip if no dates in this stratum
        if (nrow(stratum_dates) == 0) next
        
        # Determine number of samples for this stratum
        n_samples <- num_samples_per_stratum
        
        # For festivals and holidays, use all dates
        if (day_t == "Festival" || day_t == "Holiday") {
          n_samples <- nrow(stratum_dates)
        }
        
        # Ensure we don't try to sample more than available
        n_samples <- min(n_samples, nrow(stratum_dates))
        
        if (n_samples == 0) next
        
        # Sample dates from the stratum (if possible)
        sampled_indices <- sample(1:nrow(stratum_dates), n_samples, replace = FALSE)
        
        # For each sampled date, select a random starting hour
        for (idx in sampled_indices) {
          date_row <- stratum_dates[idx, ]
          d <- date_row$date
          
          start_hour <- sample(hours, 1)
          end_hour <- start_hour + 2
          
          # Format the date string
          month_str <- months(d)
          day_num <- day(d)
          year_num <- year(d)
          weekday <- weekdays(d)
          
          date_str <- paste(month_str, day_num, year_num, sep = " ")
          
          # Format times with AM/PM
          start_ampm <- if (start_hour < 12) {
            paste0(start_hour, ":00 AM")
          } else if (start_hour == 12) {
            "12:00 PM"
          } else {
            paste0(start_hour - 12, ":00 PM")
          }
          
          end_ampm <- if (end_hour < 12) {
            paste0(end_hour, ":00 AM")
          } else if (end_hour == 12) {
            "12:00 PM"
          } else {
            paste0(end_hour - 12, ":00 PM")
          }
          
          # Add to results
          new_row <- data.frame(
            site = site,
            date = date_str,
            raw_date = d,  # Add raw date for sorting
            day = weekday,
            month = as.character(date_row$month_name),
            day_type = day_t,
            start_time = start_ampm,
            end_time = end_ampm,
            stringsAsFactors = FALSE
          )
          
          results <- rbind(results, new_row)
        }
      }
    }
  }
  
  # Sort by site, date, and start time
  results <- results[order(results$site, results$raw_date), ]
  
  # Remove the raw_date column used for sorting
  results$raw_date <- NULL
  
  return(results)
}

#..............................................................................#
# Generate sampling windows
sampling_schedule <- generate_sampling_windows(
  all_dates,
  sites,
  sampling_hours,
  num_samples_per_stratum = 3  # 3 samples per month per day type (weekday/weekend) per site
)

# Reorder columns
sampling_schedule <- sampling_schedule[, c("site", "date", "day", "month", "day_type", "start_time", "end_time")]

#..............................................................................#
# Print summary statistics using dplyr
summary_stats <- sampling_schedule %>%
  group_by(site, month, day_type) %>%
  summarise(count = n(), .groups = "drop")


cat("Summary of sampling schedule:\n")
print(summary_stats)


cat("\nDetailed sampling schedule:\n")
print(sampling_schedule)

#..............................................................................#
# Write to CSV
write.csv(sampling_schedule, "recreation_survey_sampling_schedule.csv", row.names = FALSE)

#..............................................................................#
