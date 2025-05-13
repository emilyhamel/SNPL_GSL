#..............................................................................#      
#........ Snowy Plover Recreation Survey Sampling Windows Generator ...........#
#
# For 2 sites, May 21-August 31, with one time slot per survey type per site per day
# Ensuring no time overlap between surveys
#..............................................................................#

library(lubridate)
library(dplyr)
library(tidyr)

# Set working directory
setwd("C:/Users/emily.hamel/Box/-.Emily.Hamel Individual/GSL/SNPL")
# NOTE: working directory will need to be changed based on the user.
# The file path identified will be where the output files will be saved.

# For reproducibility
set.seed(123)

#..............................................................................#
# Define survey period (May 21 through August 31, 2025)
start_date <- as.Date("2025-05-21")
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
sampling_hours <- seq(6, 18, by = 1) # All possible starting hours from 6AM to 6PM

#..............................................................................#
# Helper function to parse time strings to numeric hours
parse_time_to_hour <- function(time_str) {
  hour_num <- 0
  if (grepl("AM", time_str)) {
    hour_num <- as.numeric(sub(":00 AM", "", time_str))
    if (hour_num == 12) hour_num <- 0
  } else {
    hour_num <- as.numeric(sub(":00 PM", "", time_str))
    if (hour_num != 12) hour_num <- hour_num + 12
  }
  return(hour_num)
}

# Helper function to format hours to time strings
format_hour_to_time <- function(hour) {
  if (hour < 12) {
    return(paste0(hour, ":00 AM"))
  } else if (hour == 12) {
    return("12:00 PM")
  } else {
    return(paste0(hour - 12, ":00 PM"))
  }
}

#..............................................................................#
generate_non_overlapping_surveys <- function(dates_df, site_names, 
                                             num_dates_per_stratum = 8) {
  
  # Create empty data frames for both surveys
  observational_results <- data.frame()
  intercept_results <- data.frame()
  
  # Process each month
  for (m in unique(dates_df$month)) {
    month_dates <- subset(dates_df, month == m)
    
    # Process each day type within the month
    for (day_t in unique(month_dates$day_type)) {
      stratum_dates <- subset(month_dates, day_type == day_t)
      
      # Skip if no dates in this stratum
      if (nrow(stratum_dates) == 0) next
      
      # Determine number of dates to sample based on day type
      # Increased sampling for better coverage
      if (day_t == "Weekday") {
        n_dates <- ceiling(num_dates_per_stratum * 1.5)  # More weekdays
      } else if (day_t == "Weekend") {
        n_dates <- num_dates_per_stratum  # Standard number for weekends
      } else {
        # For festivals and holidays, use all dates
        n_dates <- nrow(stratum_dates)
      }
      
      # Ensure we don't try to sample more than available
      n_dates <- min(n_dates, nrow(stratum_dates))
      
      if (n_dates == 0) next
      
      # Sample dates from the stratum
      sampled_indices <- sample(1:nrow(stratum_dates), n_dates, replace = FALSE)
      
      # For each sampled date
      for (idx in sampled_indices) {
        date_row <- stratum_dates[idx, ]
        d <- date_row$date
        
        # Get available hours for the entire day
        available_hours <- sampling_hours
        
        # Make sure there are enough available hours to choose 4 non-overlapping 2-hour windows
        # (1 window per survey type per site)
        if (length(available_hours) < 4) {
          warning(paste("Not enough hours for", d, "- Need at least 4 hours"))
          next
        }
        
        # Randomly select 4 unique start hours (for 4 total time slots)
        selected_hours <- sample(available_hours, 4, replace = FALSE)
        
        # Assign hours to site/survey combinations (1 slot per site per survey type)
        assignments <- data.frame(
          site = rep(site_names, each = 2),
          survey = rep(c("Observational", "Intercept"), times = 2),
          stringsAsFactors = FALSE
        )
        
        # Randomly assign the 4 selected hours to the 4 site/survey combinations
        assignments$start_hour <- sample(selected_hours, 4, replace = FALSE)
        
        # For each assignment, generate the survey entry
        for (i in 1:nrow(assignments)) {
          this_site <- assignments$site[i]
          this_survey <- assignments$survey[i]
          start_hour <- assignments$start_hour[i]
          end_hour <- start_hour + 2
          
          # Format date and time
          date_str <- format(d, "%B %d %Y")
          weekday <- weekdays(d)
          start_ampm <- format_hour_to_time(start_hour)
          end_ampm <- format_hour_to_time(end_hour)
          
          new_row <- data.frame(
            survey = this_survey,
            site = this_site,
            date = date_str,
            raw_date = d,
            day = weekday,
            month = as.character(date_row$month_name),
            day_type = day_t,
            start_time = start_ampm,
            end_time = end_ampm,
            stringsAsFactors = FALSE
          )
          
          # Add to correct results frame
          if (this_survey == "Observational") {
            observational_results <- rbind(observational_results, new_row)
          } else {
            intercept_results <- rbind(intercept_results, new_row)
          }
        }
      }
    }
  }
  
  # Combine the results from both surveys
  combined_results <- rbind(observational_results, intercept_results)
  
  # Sort by date, site, and start time
  combined_results <- combined_results %>%
    mutate(
      sort_date = as.Date(raw_date),
      sort_hour = sapply(start_time, parse_time_to_hour)
    ) %>%
    arrange(sort_date, site, sort_hour, survey) %>%
    select(-sort_date, -sort_hour)
  
  return(list(
    combined = combined_results,
    observational = observational_results,
    intercept = intercept_results
  ))
}

#..............................................................................#
# Generate both surveys with guaranteed non-overlapping time slots
# Increased the number of samples per stratum for better coverage
survey_results <- generate_non_overlapping_surveys(
  all_dates,
  sites,
  num_dates_per_stratum = 8  # Increased from 6 to ensure better coverage
)

# Extract the results
combined_schedule <- survey_results$combined
observational_schedule <- survey_results$observational
intercept_schedule <- survey_results$intercept

#..............................................................................#
# Comprehensive verification checks

# Check for overlapping time slots between the two survey types
cat("\n Verifying no overlaps between survey types... \n")
verification_df <- combined_schedule %>%
  select(survey, site, raw_date, start_time) %>%
  mutate(hour = sapply(start_time, parse_time_to_hour))

overlap_test <- verification_df %>%
  group_by(site, raw_date, hour) %>%
  summarise(count = n(), surveys = paste(unique(survey), collapse = ", "), .groups = "drop") %>%
  filter(count > 1)

if(nrow(overlap_test) > 0) {
  cat("ERROR: Found overlapping time slots between surveys\n")
  print(overlap_test)
} else {
  cat("No overlapping time slots found between surveys.\n")
}

# Check for exactly 1 slot per day per site for each survey type
cat("\n Verifying slot counts...\n")
slots_per_day_site_survey <- combined_schedule %>%
  group_by(survey, site, raw_date) %>%
  summarise(slot_count = n(), .groups = "drop") %>%
  filter(slot_count != 1)

if(nrow(slots_per_day_site_survey) > 0) {
  cat("ERROR: Some combinations do not have exactly 1 slot:\n")
  print(slots_per_day_site_survey)
} else {
  cat("Each survey has exactly 1 slot per day per site.\n")
}

# Verify total slots per day is 4 (1 per survey type per site)
cat("\n Verifying total daily slots... \n")
total_slots_per_day <- combined_schedule %>%
  group_by(raw_date) %>%
  summarise(total_slots = n(), .groups = "drop") %>%
  filter(total_slots != 4)

if(nrow(total_slots_per_day) > 0) {
  cat("ERROR: Some days do not have exactly 4 total slots:\n")
  print(total_slots_per_day)
} else {
  cat("Each day has exactly 4 total slots (2 per site, 1 per survey type per site).\n")
}

# Check distribution of survey times across the day
cat("\n Analyzing time distribution... \n")
time_distribution <- combined_schedule %>%
  mutate(hour = sapply(start_time, parse_time_to_hour)) %>%
  group_by(survey, hour) %>%
  summarise(count = n(), .groups = "drop") %>%
  arrange(survey, hour)

cat("Time distribution across the day:\n")
print(time_distribution)

# Check stratification results
cat("\n Stratification summary... \n")
strat_summary <- combined_schedule %>%
  group_by(survey, month, day_type) %>%
  summarise(
    unique_dates = n_distinct(raw_date),
    total_slots = n(),
    .groups = "drop"
  ) %>%
  arrange(survey, month, day_type)

cat("Stratification results by month and day type:\n")
print(strat_summary)

# Overall summary of coverage
cat("\n Overall sampling coverage... \n")
total_unique_days <- n_distinct(combined_schedule$raw_date)
total_days_in_period <- as.integer(end_date - start_date) + 1
coverage_percentage <- round((total_unique_days / total_days_in_period) * 100, 1)

cat("Total unique days sampled:", total_unique_days, "out of", total_days_in_period, 
    "days in the survey period (", coverage_percentage, "% coverage)\n", sep="")

#..............................................................................#
# Write to CSV
write.csv(combined_schedule, "recreation_survey_sampling_schedule.csv", row.names = FALSE)

# Write separate CSVs for each survey
write.csv(observational_schedule, "recreation_Observational_sampling_schedule.csv", row.names = FALSE)
write.csv(intercept_schedule, "recreation_Intercept_sampling_schedule.csv", row.names = FALSE)

#..............................................................................#
