"""
Langchain Integration Service
AI-powered features for restaurant planning using Langchain and OpenAI

NOTE: This file is currently unused. The AI functionality has been moved to
agentic_ai/restaurant_planner.py and services/ai_agent.py.
This file is kept for reference but is not imported anywhere in the codebase.
"""
import os
import json
from config import Config
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import logging

logger = logging.getLogger(__name__)

class LangchainService:
    """Service class for Langchain AI operations"""
    
    def __init__(self):
        """Initialize Langchain service"""
        try:
            if not Config.OPENAI_API_KEY:
                logger.warning("OpenAI API key not configured. Langchain features will be limited.")
                self.llm = None
            else:
                self.llm = ChatOpenAI(
                    model="gpt-3.5-turbo",
                    temperature=0.7,
                    openai_api_key=Config.OPENAI_API_KEY
                )
                logger.info("Langchain service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Langchain: {str(e)}")
            self.llm = None
    
    def get_menu_recommendations(self, restaurant, menus, preferences):
        """
        Get AI-powered menu recommendations based on preferences
        
        Args:
            restaurant: Restaurant data dictionary
            menus: List of menu dictionaries
            preferences: User preferences dictionary (e.g., dietary_restrictions, price_range, cuisine_preferences)
        
        Returns:
            List of recommended menu items with explanations
        """
        if not self.llm:
            return self._fallback_menu_recommendations(menus, preferences)
        
        try:
            # Extract menu items from all menus
            all_items = []
            for menu in menus:
                items = menu.get('items', [])
                for item in items:
                    item['menu_name'] = menu.get('name', 'Unknown Menu')
                    all_items.append(item)
            
            # Build prompt
            system_prompt = """You are a helpful restaurant assistant that recommends menu items based on customer preferences.
            Analyze the menu items and customer preferences to provide personalized recommendations.
            Return your response as a JSON array with the following structure:
            [
                {
                    "item_name": "name of the menu item",
                    "reason": "why this item matches the customer's preferences",
                    "match_score": 0.0-1.0
                }
            ]
            Sort by match_score descending. Return top 5 recommendations."""
            
            human_prompt = f"""Restaurant: {restaurant.get('name', 'Unknown')}
            Cuisine Type: {restaurant.get('cuisine_type', 'Unknown')}
            
            Available Menu Items:
            {json.dumps(all_items, indent=2)}
            
            Customer Preferences:
            {json.dumps(preferences, indent=2)}
            
            Please recommend menu items that best match the customer's preferences."""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = self.llm(messages)
            response_text = response.content
            
            # Try to parse JSON from response
            try:
                # Extract JSON from markdown code blocks if present
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()
                
                recommendations = json.loads(response_text)
                if isinstance(recommendations, list):
                    return recommendations
                else:
                    return [recommendations]
            except json.JSONDecodeError:
                # If JSON parsing fails, return structured response
                logger.warning("Failed to parse JSON from LLM response")
                return self._fallback_menu_recommendations(menus, preferences)
                
        except Exception as e:
            logger.error(f"Error getting menu recommendations: {str(e)}")
            return self._fallback_menu_recommendations(menus, preferences)
    
    def _fallback_menu_recommendations(self, menus, preferences):
        """Fallback recommendations when LLM is not available"""
        recommendations = []
        for menu in menus:
            items = menu.get('items', [])
            for item in items[:3]:  # Top 3 from each menu
                recommendations.append({
                    "item_name": item.get('name', 'Unknown'),
                    "reason": "Popular item",
                    "match_score": 0.7
                })
        return recommendations[:5]
    
    def get_reservation_recommendations(self, restaurant, reservations, tables, party_size, preferred_date):
        """
        Get AI-powered reservation time recommendations
        
        Args:
            restaurant: Restaurant data dictionary
            reservations: List of existing reservations
            tables: List of available tables
            party_size: Number of guests
            preferred_date: Preferred reservation date
        
        Returns:
            List of recommended reservation times with availability info
        """
        if not self.llm:
            return self._fallback_reservation_recommendations(tables, party_size)
        
        try:
            # Find available tables for party size
            available_tables = [t for t in tables if t.get('capacity', 0) >= party_size and t.get('status') == 'available']
            
            # Get booked times
            booked_times = [r.get('time') for r in reservations if r.get('status') == 'confirmed']
            
            system_prompt = """You are a restaurant reservation assistant. Analyze table availability and existing reservations to recommend the best reservation times.
            Return your response as a JSON array:
            [
                {
                    "time": "HH:MM",
                    "table_number": table number,
                    "reason": "why this time is recommended",
                    "availability_score": 0.0-1.0
                }
            ]
            Sort by availability_score descending. Return top 5 recommendations."""
            
            human_prompt = f"""Restaurant: {restaurant.get('name', 'Unknown')}
            Preferred Date: {preferred_date}
            Party Size: {party_size} guests
            
            Available Tables:
            {json.dumps(available_tables, indent=2)}
            
            Already Booked Times:
            {json.dumps(booked_times, indent=2)}
            
            Restaurant Hours: {restaurant.get('opening_hours', {})}
            
            Recommend the best available reservation times for this party size."""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = self.llm(messages)
            response_text = response.content
            
            # Parse JSON response
            try:
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()
                
                recommendations = json.loads(response_text)
                if isinstance(recommendations, list):
                    return recommendations
                else:
                    return [recommendations]
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON from LLM response")
                return self._fallback_reservation_recommendations(tables, party_size)
                
        except Exception as e:
            logger.error(f"Error getting reservation recommendations: {str(e)}")
            return self._fallback_reservation_recommendations(tables, party_size)
    
    def _fallback_reservation_recommendations(self, tables, party_size):
        """Fallback recommendations when LLM is not available"""
        recommendations = []
        available_tables = [t for t in tables if t.get('capacity', 0) >= party_size]
        
        # Suggest common dinner times
        common_times = ["18:00", "18:30", "19:00", "19:30", "20:00"]
        for i, time in enumerate(common_times[:len(available_tables)]):
            if i < len(available_tables):
                recommendations.append({
                    "time": time,
                    "table_number": available_tables[i].get('table_number', i+1),
                    "reason": "Popular dining time",
                    "availability_score": 0.8 - (i * 0.1)
                })
        
        return recommendations
    
    def chat(self, restaurant, menus, message):
        """
        AI chat endpoint for restaurant queries
        
        Args:
            restaurant: Restaurant data dictionary
            menus: List of menu dictionaries
            message: User message
        
        Returns:
            AI response string
        """
        if not self.llm:
            return "I'm sorry, AI chat is currently unavailable. Please contact the restaurant directly."
        
        try:
            # Extract menu summary
            menu_summary = []
            for menu in menus:
                items = menu.get('items', [])
                menu_summary.append({
                    "menu_name": menu.get('name', 'Unknown'),
                    "item_count": len(items),
                    "categories": list(set([item.get('category', 'Other') for item in items]))
                })
            
            system_prompt = f"""You are a helpful assistant for {restaurant.get('name', 'the restaurant')}.
            You can help customers with:
            - Menu questions and recommendations
            - Reservation information
            - Restaurant details and hours
            - Dietary restrictions and allergies
            
            Be friendly, helpful, and concise. If you don't know something, suggest contacting the restaurant directly.
            
            Restaurant Information:
            Name: {restaurant.get('name', 'Unknown')}
            Cuisine: {restaurant.get('cuisine_type', 'Unknown')}
            Address: {restaurant.get('address', 'Unknown')}
            Phone: {restaurant.get('phone', 'Unknown')}
            Email: {restaurant.get('email', 'Unknown')}
            
            Available Menus:
            {json.dumps(menu_summary, indent=2)}"""
            
            human_prompt = f"Customer Question: {message}"
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = self.llm(messages)
            return response.content
            
        except Exception as e:
            logger.error(f"Error in AI chat: {str(e)}")
            return "I'm sorry, I encountered an error. Please try again or contact the restaurant directly."

